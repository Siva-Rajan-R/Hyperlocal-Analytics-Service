
from datetime import datetime
from typing import Optional

from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.stockmovadj_schemas.request_schemas import StockMovAdjAnalyticsSchema
from .analytics_base_repo import AnalyticsBaseRepo


def _extract_date_str(val) -> str:
    if not val:
        return datetime.utcnow().strftime("%Y-%m-%d")
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return datetime.utcnow().strftime("%Y-%m-%d")

def _parse_datetime(val) -> datetime:
    if isinstance(val, datetime):
        return val
    if val:
        try:
            s = str(val).strip().replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except Exception:
            pass
    return datetime.utcnow()


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

        daily_groups = {}

        for item in payload.datas:
            total += 1
            qty = abs(float(item.stocks or 0))
            t_upper = str(item.type or "").upper()
            is_inc = t_upper in (
                "IN", "INCREMENT", "ADD", "PLUS", "PURCHASE", "PO_PURCHASE",
                "SALE_RETURN", "SALES_RETURN", "POSITIVE_ADJUSTMENT"
            ) and not (item.stocks is not None and float(item.stocks) < 0)

            if is_inc:
                increments += qty
            else:
                decrements += qty

            d = _extract_date_str(getattr(item, "created_at", None))
            if d not in daily_groups:
                daily_groups[d] = {
                    "total": 0,
                    "increments": 0.0,
                    "decrements": 0.0,
                    "latest_created": getattr(item, "created_at", None)
                }
            daily_groups[d]["total"] += 1
            if is_inc:
                daily_groups[d]["increments"] += qty
            else:
                daily_groups[d]["decrements"] += qty

            from .prod_inv_repo import prod_inv_repo
            await prod_inv_repo.apply_stockmovadj(
                shop_id=payload.shop_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                batch_id=item.batch_id,
                stocks=qty,
                type=item.type,
            )

        increments = round(float(increments), 2)
        decrements = round(float(decrements), 2)
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

        for d, stats in daily_groups.items():
            ts = _parse_datetime(stats["latest_created"]) if stats["latest_created"] else datetime.utcnow()
            await self.daily.update_one(
                {
                    "shop_id": payload.shop_id,
                    "date": d,
                },
                {
                    "$inc": {
                        "total_stockmovadj": stats["total"],
                        "total_stockmovadj_increments": round(float(stats["increments"]), 2),
                        "total_stockmovadj_decrements": round(float(stats["decrements"]), 2),
                    },
                    "$set": {
                        "shop_id": payload.shop_id,
                        "date": d,
                        "timestamp": ts,
                    },
                },
                upsert=True,
            )
        return {"status": "success"}

    async def get_overall(self, shop_id: str):
        res = await self.overall.find_one(
            {"shop_id": shop_id},
            {"_id": 0},
        )
        if res:
            if "total_stockmovadj_increments" in res and res["total_stockmovadj_increments"] is not None:
                res["total_stockmovadj_increments"] = round(float(res["total_stockmovadj_increments"]), 2)
            if "total_stockmovadj_decrements" in res and res["total_stockmovadj_decrements"] is not None:
                res["total_stockmovadj_decrements"] = round(float(res["total_stockmovadj_decrements"]), 2)
        return res

    async def daily_history(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        filters = {"shop_id": shop_id}

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = _extract_date_str(start_date)
            if end_date:
                date_filter["$lte"] = _extract_date_str(end_date)
            filters["date"] = date_filter

        return await self.find_many(
            filters=filters,
            sort=[("date", -1)],
        )

    async def trend(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        filters = {"shop_id": shop_id}

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = _extract_date_str(start_date)
            if end_date:
                date_filter["$lte"] = _extract_date_str(end_date)
            filters["date"] = date_filter

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

    async def dashboard(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        return {
            "overall": await self.get_overall(shop_id),
            "daily": await self.daily_history(shop_id, start_date=start_date, end_date=end_date),
            "trend": await self.trend(shop_id, start_date=start_date, end_date=end_date),
        }

    async def delete_shop(self, shop_id: str):
        await self.overall.delete_one({"shop_id": shop_id})
        await self.daily.delete_many({"shop_id": shop_id})


stockmovadj_repo = StockMovAdjRepo()
