
from datetime import datetime
from typing import Optional

from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.supplier_schemas.request_schemas import SupplierAnalyticsSchema
from .analytics_base_repo import AnalyticsBaseRepo


class SupplierRepo(AnalyticsBaseRepo):

    def __init__(self):
        super().__init__(ANALYTICS_COLLECTIONS["supplier"]["overall"])
        self.overall = ANALYTICS_COLLECTIONS["supplier"]["overall"]
        self.breakdown = ANALYTICS_COLLECTIONS["supplier"]["breakdown"]

    async def create_indexes(self):
        await self.overall.create_index([("shop_id", 1)], unique=True)
        await self.breakdown.create_index([("shop_id", 1), ("supplier_id", 1)], unique=True)
        await self.breakdown.create_index([("shop_id", 1), ("timestamp", -1)])

    async def process_event(self, payload: SupplierAnalyticsSchema):
        for item in payload.datas:
            outstanding = float(item.outstanding_amounts or 0)
            cleared = float(item.cleared_amounts or 0)

            if getattr(payload, "action", "create") == "delete":
                await self.breakdown.delete_one(
                    {
                        "shop_id": payload.shop_id,
                        "supplier_id": item.supplier_id,
                    }
                )
            else:
                await self.breakdown.update_one(
                    {
                        "shop_id": payload.shop_id,
                        "supplier_id": item.supplier_id,
                    },
                    {
                        "$set": {
                            "shop_id": payload.shop_id,
                            "supplier_id": item.supplier_id,
                            "total_outstandings": outstanding,
                            "total_cleared_amounts": cleared,
                            "timestamp": datetime.utcnow(),
                        },
                        "$setOnInsert": {
                            "total_purchases": 0,
                            "total_purchase_amounts": 0.0,
                        },
                    },
                    upsert=True,
                )

        pipeline = [
            {"$match": {"shop_id": payload.shop_id}},
            {
                "$group": {
                    "_id": "$shop_id",
                    "total_suppliers": {"$sum": 1},
                    "total_outstandings": {"$sum": "$total_outstandings"},
                    "total_cleared_amounts": {"$sum": "$total_cleared_amounts"},
                }
            }
        ]
        agg_res = await self.breakdown.aggregate(pipeline).to_list(1)
        if agg_res:
            tot = agg_res[0]
            await self.overall.update_one(
                {"shop_id": payload.shop_id},
                {
                    "$set": {
                        "shop_id": payload.shop_id,
                        "total_suppliers": tot.get("total_suppliers", 0),
                        "total_outstandings": float(tot.get("total_outstandings", 0.0)),
                        "total_cleared_amounts": float(tot.get("total_cleared_amounts", 0.0)),
                        "timestamp": datetime.utcnow(),
                    }
                },
                upsert=True,
            )
        return {"status": "success"}

    async def apply_purchase(
        self,
        shop_id: str,
        supplier_id: str,
        amount: float,
        total_purchase: int = 1,
    ):
        await self.breakdown.update_one(
            {
                "shop_id": shop_id,
                "supplier_id": supplier_id,
            },
            {
                "$inc": {
                    "total_purchases": total_purchase,
                    "total_purchase_amounts": amount,
                },
                "$set": {"timestamp": datetime.utcnow()},
            },
            upsert=True,
        )

    async def get_overall(self, shop_id: str):
        return await self.overall.find_one({"shop_id": shop_id}, {"_id": 0})

    async def get_supplier(self, shop_id: str, supplier_id: str):
        return await self.breakdown.find_one(
            {
                "shop_id": shop_id,
                "supplier_id": supplier_id,
            },
            {"_id": 0},
        )

    async def list_suppliers(
        self,
        shop_id: str,
        page: int = 1,
        page_size: int = 20,
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

        return await self.paginate_query(
            filters=filters,
            page=page,
            page_size=page_size,
        )

    async def top_suppliers(self, shop_id: str, limit: int = 10):
        cursor = self.breakdown.find(
            {"shop_id": shop_id},
            {"_id": 0}
        ).sort("total_purchases", -1).limit(limit)
        return await cursor.to_list(length=None)

    async def supplier_trend(
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
                    "total_purchases": {"$sum": "$total_purchases"},
                    "total_outstandings": {"$sum": "$total_outstandings"},
                    "total_cleared_amounts": {"$sum": "$total_cleared_amounts"},
                }
            },
            {"$sort": {"_id": 1}},
        ])

    async def dashboard(self, shop_id: str):
        overall = await self.get_overall(shop_id)
        top = await self.top_suppliers(shop_id, 5)
        trend = await self.supplier_trend(shop_id)

        return {
            "overall": overall,
            "top_suppliers": top,
            "trend": trend,
        }

    async def delete_shop(self, shop_id: str):
        await self.overall.delete_one({"shop_id": shop_id})
        await self.breakdown.delete_many({"shop_id": shop_id})


supplier_repo = SupplierRepo()
