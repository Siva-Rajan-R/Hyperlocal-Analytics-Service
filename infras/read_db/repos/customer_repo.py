
from datetime import datetime
from typing import Optional
from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.customer_schemas.request_schemas import CustomerAnalyticsSchema
from .analytics_base_repo import AnalyticsBaseRepo


class CustomerRepo(AnalyticsBaseRepo):

    def __init__(self):
        super().__init__(ANALYTICS_COLLECTIONS["customer"]["overall"])
        self.overall = ANALYTICS_COLLECTIONS["customer"]["overall"]
        self.breakdown = ANALYTICS_COLLECTIONS["customer"]["breakdown"]

    async def create_indexes(self):
        await self.overall.create_index([("shop_id", 1)], unique=True)
        await self.breakdown.create_index([("shop_id", 1), ("customer_id", 1)], unique=True)
        await self.breakdown.create_index([("shop_id", 1), ("timestamp", -1)])

    async def process_event(self, payload: CustomerAnalyticsSchema):
        total_credit = 0.0
        total_outstanding = 0.0
        total_cleared = 0.0

        for item in payload.datas:
            credit = item.credit_limit or 0
            outstanding = (item.outstanding_amounts or 0) - (item.cleared_amounts or 0)
            cleared = item.cleared_amounts or 0

            total_credit += credit
            total_outstanding += outstanding
            total_cleared += cleared

            if getattr(payload, "action", "create") == "delete":
                await self.breakdown.delete_one(
                    {
                        "shop_id": payload.shop_id,
                        "customer_id": item.customer_id,
                    }
                )
            else:
                await self.breakdown.update_one(
                    {
                        "shop_id": payload.shop_id,
                        "customer_id": item.customer_id,
                    },
                    {
                        "$inc": {
                            "total_outstandings": outstanding,
                            "total_cleared_amounts": cleared,
                            "total_credit_limits": credit,
                        },
                        "$set": {
                            "timestamp": datetime.utcnow(),
                        },
                        "$setOnInsert": {
                            "shop_id": payload.shop_id,
                            "customer_id": item.customer_id,
                            "total_settlements": 0,
                            "total_sales": 0,
                            "total_sales_amount": 0,
                        },
                    },
                    upsert=True,
                )

        customer_count = await self.breakdown.count_documents({"shop_id": payload.shop_id})

        await self.overall.update_one(
            {"shop_id": payload.shop_id},
            {
                "$set": {
                    "shop_id": payload.shop_id,
                    "timestamp": datetime.utcnow(),
                    "total_customers": customer_count,
                },
                "$inc": {
                    "total_credit_limits": total_credit,
                    "total_outstandings": total_outstanding,
                    "total_cleared_amounts": total_cleared,
                },
                "$setOnInsert": {
                    "total_settlements": 0,
                },
            },
            upsert=True,
        )

    async def apply_sale(
        self,
        shop_id: str,
        customer_id: str,
        amount: float,
        sales_type: str,
    ):
        is_online = (sales_type or "").upper() == "ONLINE"
        
        inc_fields = {
            "total_sales": 1,
            "total_sales_amount": amount,
        }
        if is_online:
            inc_fields["total_online_sales"] = 1
            inc_fields["total_online_sales_amount"] = amount
        else:
            inc_fields["total_offline_sales"] = 1
            inc_fields["total_offline_sales_amount"] = amount

        await self.breakdown.update_one(
            {
                "shop_id": shop_id,
                "customer_id": customer_id,
            },
            {
                "$inc": inc_fields,
                "$set": {"timestamp": datetime.utcnow()},
            },
            upsert=True,
        )

    async def get_overall(self, shop_id: str):
        return await self.overall.find_one({"shop_id": shop_id}, {"_id": 0})

    async def get_customer(self, shop_id: str, customer_id: str):
        return await self.breakdown.find_one(
            {"shop_id": shop_id, "customer_id": customer_id},
            {"_id": 0},
        )

    async def list_customers(
        self,
        shop_id: str,
        page: int = 1,
        page_size: int = 20,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sales_type: Optional[str] = None,
    ):
        filters = {"shop_id": shop_id}
        if start_date or end_date:
            filters["timestamp"] = {}
            if start_date:
                filters["timestamp"]["$gte"] = start_date
            if end_date:
                filters["timestamp"]["$lte"] = end_date
                
        if sales_type:
            if sales_type.upper() == "ONLINE":
                filters["total_online_sales"] = {"$gt": 0}
            elif sales_type.upper() == "OFFLINE":
                filters["total_offline_sales"] = {"$gt": 0}

        return await self.paginate_query(filters, page, page_size)

    async def top_customers(self, shop_id: str, limit: int = 10, sales_type: Optional[str] = None):
        sort_field = "total_sales_amount"
        if sales_type:
            if sales_type.upper() == "ONLINE":
                sort_field = "total_online_sales_amount"
            elif sales_type.upper() == "OFFLINE":
                sort_field = "total_offline_sales_amount"

        cursor = self.breakdown.find(
            {"shop_id": shop_id},
            {"_id": 0}
        ).sort(sort_field, -1).limit(limit)
        return await cursor.to_list(length=None)

    async def customer_trend(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        filters = {"shop_id": shop_id}
        if start_date or end_date:
            filters["timestamp"] = {}
            if start_date:
                filters["timestamp"]["$gte"] = start_date
            if end_date:
                filters["timestamp"]["$lte"] = end_date

        return await self.aggregate([
            {"$match": filters},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$timestamp",
                        }
                    },
                    "customers": {"$sum": 1},
                    "outstanding": {"$sum": "$total_outstandings"},
                    "cleared": {"$sum": "$total_cleared_amounts"},
                }
            },
            {"$sort": {"_id": 1}},
        ])

    async def dashboard(self, shop_id: str):
        return {
            "overall": await self.get_overall(shop_id),
            "top_customers": await self.top_customers(shop_id, 5),
            "trend": await self.customer_trend(shop_id),
        }

    async def delete_shop(self, shop_id: str):
        await self.overall.delete_one({"shop_id": shop_id})
        await self.breakdown.delete_many({"shop_id": shop_id})


customer_repo = CustomerRepo()
