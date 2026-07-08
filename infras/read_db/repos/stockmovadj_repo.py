
from datetime import datetime
from typing import Optional

from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.stockmovadj_schemas.request_schemas import StockMovAdjAnalyticsSchema
from .analytics_base_repo import AnalyticsBaseRepo


class StockMovAdjRepo(AnalyticsBaseRepo):

    def __init__(self):
        super().__init__(ANALYTICS_COLLECTIONS["stockmovadj"]["overall"])
        self.overall = ANALYTICS_COLLECTIONS["stockmovadj"]["overall"]
        self.daily = ANALYTICS_COLLECTIONS["stockmovadj"]["daily"]

    async def create_indexes(self):
        await self.overall.create_index([("shop_id", 1)], unique=True)
        await self.daily.create_index([("shop_id", 1), ("date", 1)], unique=True)
        await self.daily.create_index([("shop_id", 1), ("timestamp", -1)])

    async def process_event(self, payload: StockMovAdjAnalyticsSchema):
        increments = 0.0
        decrements = 0.0
        total = 0

        today = datetime.utcnow().strftime("%Y-%m-%d")

        for item in payload.datas:
            total += 1
            qty = item.stocks or 0

            if (item.type or "").upper() in ("IN", "INCREMENT", "ADD", "PLUS"):
                increments += qty
            else:
                decrements += qty

            from .prod_inv_repo import prod_inv_repo
            await prod_inv_repo.apply_stockmovadj(
                shop_id=payload.shop_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                batch_id=item.batch_id,
                stocks=qty,
                type=item.type,
            )

        update = {
            "$inc": {
                "total_stockmovadj": total,
                "total_stockmovadj_increments": increments,
                "total_stockmovadj_decrements": decrements,
            },
            "$set": {
                "shop_id": payload.shop_id,
                "timestamp": datetime.utcnow(),
            },
        }

        await self.overall.update_one(
            {"shop_id": payload.shop_id},
            update,
            upsert=True,
        )

        await self.daily.update_one(
            {
                "shop_id": payload.shop_id,
                "date": today,
            },
            {
                "$inc": {
                    "total_stockmovadj": total,
                    "total_stockmovadj_increments": increments,
                    "total_stockmovadj_decrements": decrements,
                },
                "$set": {
                    "shop_id": payload.shop_id,
                    "date": today,
                    "timestamp": datetime.utcnow(),
                },
            },
            upsert=True,
        )

    async def get_overall(self, shop_id: str):
        return await self.overall.find_one(
            {"shop_id": shop_id},
            {"_id": 0},
        )

    async def daily_history(
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

    async def trend(
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
                    "_id": "$date",
                    "adjustments": {"$sum": "$total_stockmovadj"},
                    "increments": {"$sum": "$total_stockmovadj_increments"},
                    "decrements": {"$sum": "$total_stockmovadj_decrements"},
                }
            },
            {"$sort": {"_id": 1}},
        ])

    async def dashboard(self, shop_id: str):
        return {
            "overall": await self.get_overall(shop_id),
            "daily": await self.daily_history(shop_id),
            "trend": await self.trend(shop_id),
        }

    async def delete_shop(self, shop_id: str):
        await self.overall.delete_one({"shop_id": shop_id})
        await self.daily.delete_many({"shop_id": shop_id})


stockmovadj_repo = StockMovAdjRepo()
