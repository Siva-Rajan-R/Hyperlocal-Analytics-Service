
from datetime import datetime
from typing import Optional

from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.prodinv_schemas.request_schemas import ProdInvAnalyticsSchema
from .analytics_base_repo import AnalyticsBaseRepo


class ProdInvRepo(AnalyticsBaseRepo):

    def __init__(self):
        super().__init__(ANALYTICS_COLLECTIONS["prodinv"]["overall"])
        self.overall = ANALYTICS_COLLECTIONS["prodinv"]["overall"]
        self.breakdown = ANALYTICS_COLLECTIONS["prodinv"]["breakdown"]

    async def create_indexes(self):
        await self.overall.create_index([("shop_id", 1)], unique=True)
        await self.breakdown.create_index(
            [("shop_id", 1), ("product_id", 1), ("variant_id", 1), ("batch_id", 1)],
            unique=True,
        )
        await self.breakdown.create_index([("shop_id", 1), ("timestamp", -1)])

    async def process_inventory_sync(self, payload: ProdInvAnalyticsSchema):
        active = inactive = 0
        total_stock = low_stock = no_stock = 0.0

        for item in payload.datas:
            active += 1 if item.is_active else 0
            inactive += 0 if item.is_active else 1

            total_stock += item.stocks or 0
            low_stock += item.low_stocks or 0
            no_stock += item.no_stocks or 0

            await self.breakdown.update_one(
                {
                    "shop_id": payload.shop_id,
                    "product_id": item.product_id,
                    "variant_id": "",
                    "batch_id": "",
                },
                {
                    "$set": {
                        "shop_id": payload.shop_id,
                        "product_id": item.product_id,
                        "variant_id": "",
                        "batch_id": "",
                        "is_active": item.is_active,
                        "stocks": item.stocks or 0,
                        "low_stocks": item.low_stocks or 0,
                        "no_stocks": item.no_stocks or 0,
                        "timestamp": datetime.utcnow(),
                    },
                    "$setOnInsert": {
                        "total_purchases": 0,
                        "total_purchase_amounts": 0,
                        "total_purchase_outstanding_amounts": 0,
                        "total_offline_sales": 0,
                        "total_offline_sales_amount": 0,
                        "total_online_sales": 0,
                        "total_online_sales_amount": 0,
                        "total_stockmovadj_increments": 0,
                        "total_stockmovadj_decrements": 0,
                    },
                },
                upsert=True,
            )

        await self.overall.update_one(
            {"shop_id": payload.shop_id},
            {
                "$set": {
                    "shop_id": payload.shop_id,
                    "total_active_products": active,
                    "total_inactive_product": inactive,
                    "total_stocks": total_stock,
                    "total_low_stocks": low_stock,
                    "total_no_stocks": no_stock,
                    "timestamp": datetime.utcnow(),
                }
            },
            upsert=True,
        )

    async def apply_purchase(
        self,
        shop_id: str,
        product_id: str,
        variant_id: str,
        batch_id: str,
        stocks: float,
        amount: float,
        outstanding: float,
    ):
        await self.breakdown.update_one(
            {
                "shop_id": shop_id,
                "product_id": product_id,
                "variant_id": variant_id or "",
                "batch_id": batch_id or "",
            },
            {
                "$inc": {
                    "total_purchases": 1,
                    "total_purchase_amounts": amount,
                    "total_purchase_outstanding_amounts": outstanding,
                    "stocks": stocks,
                },
                "$set": {"timestamp": datetime.utcnow()},
            },
            upsert=True,
        )

        if (variant_id or "") != "" or (batch_id or "") != "":
            await self.breakdown.update_one(
                {
                    "shop_id": shop_id,
                    "product_id": product_id,
                    "variant_id": "",
                    "batch_id": "",
                },
                {
                    "$inc": {
                        "total_purchases": 1,
                        "total_purchase_amounts": amount,
                        "total_purchase_outstanding_amounts": outstanding,
                        "stocks": stocks,
                    },
                    "$set": {"timestamp": datetime.utcnow()},
                },
                upsert=True,
            )

        await self.overall.update_one(
            {"shop_id": shop_id},
            {
                "$inc": {
                    "total_stocks": stocks,
                },
                "$set": {"timestamp": datetime.utcnow()},
            },
            upsert=True,
        )

    async def apply_stockmovadj(
        self,
        shop_id: str,
        product_id: str,
        variant_id: str,
        batch_id: str,
        stocks: float,
        type: str,
    ):
        is_increment = (type or "").upper() in ("IN", "INCREMENT", "ADD", "PLUS")
        
        inc_fields = {}
        if is_increment:
            inc_fields["total_stockmovadj_increments"] = stocks
            inc_fields["stocks"] = stocks
        else:
            inc_fields["total_stockmovadj_decrements"] = stocks
            inc_fields["stocks"] = -stocks

        await self.breakdown.update_one(
            {
                "shop_id": shop_id,
                "product_id": product_id,
                "variant_id": variant_id or "",
                "batch_id": batch_id or "",
            },
            {
                "$inc": inc_fields,
                "$set": {"timestamp": datetime.utcnow()},
            },
            upsert=True,
        )

        if (variant_id or "") != "" or (batch_id or "") != "":
            await self.breakdown.update_one(
                {
                    "shop_id": shop_id,
                    "product_id": product_id,
                    "variant_id": "",
                    "batch_id": "",
                },
                {
                    "$inc": inc_fields,
                    "$set": {"timestamp": datetime.utcnow()},
                },
                upsert=True,
            )

        await self.overall.update_one(
            {"shop_id": shop_id},
            {
                "$inc": {
                    "total_stocks": stocks if is_increment else -stocks,
                },
                "$set": {"timestamp": datetime.utcnow()},
            },
            upsert=True,
        )

    async def apply_sale(
        self,
        shop_id: str,
        product_id: str,
        variant_id: str,
        batch_id: str,
        stocks: float,
        amount: float,
        sales_type: str,
    ):
        is_online = (sales_type or "").upper() == "ONLINE"
        
        inc_fields = {
            "stocks": -stocks,
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
                "product_id": product_id,
                "variant_id": variant_id or "",
                "batch_id": batch_id or "",
            },
            {
                "$inc": inc_fields,
                "$set": {"timestamp": datetime.utcnow()},
            },
            upsert=True,
        )

        if (variant_id or "") != "" or (batch_id or "") != "":
            await self.breakdown.update_one(
                {
                    "shop_id": shop_id,
                    "product_id": product_id,
                    "variant_id": "",
                    "batch_id": "",
                },
                {
                    "$inc": inc_fields,
                    "$set": {"timestamp": datetime.utcnow()},
                },
                upsert=True,
            )

        await self.overall.update_one(
            {"shop_id": shop_id},
            {
                "$inc": {
                    "total_stocks": -stocks,
                },
                "$set": {"timestamp": datetime.utcnow()},
            },
            upsert=True,
        )

    async def get_overall(self, shop_id: str):
        return await self.overall.find_one({"shop_id": shop_id}, {"_id": 0})

    async def list_products(
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
    
    async def get_product(
        self,
        shop_id: str,
        product_id: str,
    ):
        return await self.breakdown.find_one(
            {
                "shop_id": shop_id,
                "product_id": product_id,
            },
            {"_id": 0},
        )
    async def get_product_variant(
        self,
        shop_id: str,
        product_id: str,
        variant_id: str,
    ):
        return await self.breakdown.find_one(
            {
                "shop_id": shop_id,
                "product_id": product_id,
                "variant_id": variant_id,
            },
            {"_id": 0},
        )
    
    async def get_product_batch(
        self,
        shop_id: str,
        product_id: str,
        variant_id: str,
        batch_id: str,
    ):
        return await self.breakdown.find_one(
            {
                "shop_id": shop_id,
                "product_id": product_id,
                "variant_id": variant_id,
                "batch_id": batch_id,
            },
            {"_id": 0},
        )
    async def top_products(self, shop_id: str, limit: int = 10, sales_type: Optional[str] = None):
        sort_field = "total_purchase_amounts"
        if sales_type:
            if sales_type.upper() == "ONLINE":
                sort_field = "total_online_sales_amount"
            elif sales_type.upper() == "OFFLINE":
                sort_field = "total_offline_sales_amount"
            
        return await self.aggregate([
            {"$match": {"shop_id": shop_id}},
            {"$sort": {sort_field: -1}},
            {"$limit": limit},
            {"$project": {"_id": 0}},
        ])

    async def low_stock_products(self, shop_id: str):
        return await self.find_many(
            {"shop_id": shop_id, "low_stocks": {"$gt": 0}},
            sort=[("low_stocks", -1)],
        )

    async def out_of_stock_products(self, shop_id: str):
        return await self.find_many(
            {"shop_id": shop_id, "no_stocks": {"$gt": 0}},
            sort=[("timestamp", -1)],
        )

    async def dashboard(self, shop_id: str):
        return {
            "overall": await self.get_overall(shop_id),
            "top_products": await self.top_products(shop_id, 5),
            "low_stock": await self.low_stock_products(shop_id),
            "out_of_stock": await self.out_of_stock_products(shop_id),
        }

    async def delete_shop(self, shop_id: str):
        await self.overall.delete_one({"shop_id": shop_id})
        await self.breakdown.delete_many({"shop_id": shop_id})


prod_inv_repo = ProdInvRepo()
