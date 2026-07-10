
from datetime import datetime
from typing import Optional

from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.purchase_schemas.request_schemas import PurchaseAnalyticsSchema
from .analytics_base_repo import AnalyticsBaseRepo


class PurchaseRepo(AnalyticsBaseRepo):

    def __init__(self):
        super().__init__(ANALYTICS_COLLECTIONS["purchase"]["overall"])
        self.overall = ANALYTICS_COLLECTIONS["purchase"]["overall"]
        self.daily = ANALYTICS_COLLECTIONS["purchase"]["daily"]

    async def create_indexes(self):
        await self.overall.create_index([("shop_id", 1)], unique=True)
        await self.daily.create_index([("shop_id", 1), ("date", 1)], unique=True)
        await self.daily.create_index([("shop_id", 1), ("timestamp", -1)])

    async def process_event(self, payload: PurchaseAnalyticsSchema):
        print(payload.model_dump())
        total_purchase = 1
        total_amount = 0.0
        total_stock = 0.0
        total_outstanding = 0.0

        today = datetime.utcnow().strftime("%Y-%m-%d")

        for item in payload.datas:
            total_amount += item.purchase_amounts or 0
            total_stock += item.stocks or 0
            total_outstanding += item.outstanding_amounts or 0
            
            from .prod_inv_repo import prod_inv_repo
            await prod_inv_repo.apply_purchase(
                shop_id=payload.shop_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                batch_id=item.batch_id,
                stocks=item.stocks or 0.0,
                amount=item.purchase_amounts or 0.0,
                outstanding=item.outstanding_amounts or 0.0,
            )

            from .supplier_repo import supplier_repo
            await supplier_repo.apply_purchase(
                shop_id=payload.shop_id,
                supplier_id=item.supplier_id,
                amount=item.purchase_amounts or 0.0,
            )

        result = await self.overall.update_one(
            {"shop_id": payload.shop_id},
            {
                "$inc": {
                    "total_purchase": total_purchase,
                    "total_purchase_amounts": total_amount,
                    "total_purchase_stocks": total_stock,
                    "total_outstanding_amounts": total_outstanding,
                },
                "$set": {
                    "shop_id": payload.shop_id,
                    "timestamp": datetime.utcnow(),
                },
            },
            upsert=True,
        )

        print(result.matched_count)
        print(result.modified_count)
        print(result.upserted_id)

        await self.daily.update_one(
            {
                "shop_id": payload.shop_id,
                "date": today,
            },
            {
                "$inc": {
                    "total_purchase": total_purchase,
                    "total_purchase_amounts": total_amount,
                    "total_purchase_stocks": total_stock,
                    "total_outstanding_amounts": total_outstanding,
                },
                "$set": {
                    "shop_id": payload.shop_id,
                    "date": today,
                    "timestamp": datetime.utcnow(),
                },
            },
            upsert=True,
        )
        return {"success": True}

    async def get_overall(self, shop_id: str):
        return await self.overall.find_one({"shop_id": shop_id}, {"_id": 0})

    async def get_daily(
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

        return await self.find_many(
            filters=filters,
            sort=[("timestamp", 1)],
        )

    async def purchase_trend(
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

        cursor = self.daily.aggregate([
            {"$match": filters},
            {
                "$group": {
                    "_id": "$date",
                    "total_purchase": {"$sum": "$total_purchase"},
                    "total_purchase_amounts": {"$sum": "$total_purchase_amounts"},
                    "total_purchase_stocks": {"$sum": "$total_purchase_stocks"},
                    "total_outstanding_amounts": {"$sum": "$total_outstanding_amounts"},
                }
            },
            {"$sort": {"_id": 1}},
        ])
        return await cursor.to_list(length=None)

    async def dashboard(self, shop_id: str):
        return {
            "overall": await self.get_overall(shop_id),
            "trend": await self.purchase_trend(shop_id),
        }

    async def delete_shop(self, shop_id: str):
        await self.overall.delete_one({"shop_id": shop_id})
        await self.daily.delete_many({"shop_id": shop_id})


purchase_repo = PurchaseRepo()
