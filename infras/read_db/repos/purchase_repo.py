from datetime import datetime
from typing import Optional, List

from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.purchase_schemas.request_schemas import PurchaseAnalyticsSchema, PurchaseAnalyticsDatas
from .analytics_base_repo import AnalyticsBaseRepo


class PurchaseRepo(AnalyticsBaseRepo):

    def __init__(self):
        super().__init__(ANALYTICS_COLLECTIONS["purchase"]["overall"])
        self.overall = ANALYTICS_COLLECTIONS["purchase"]["overall"]
        self.breakdown = ANALYTICS_COLLECTIONS["purchase"]["breakdown"]
        self.daily = ANALYTICS_COLLECTIONS["purchase"]["daily"]

    async def create_indexes(self):
        await self.overall.create_index([("shop_id", 1)], unique=True)
        await self.breakdown.create_index([("shop_id", 1), ("purchase_id", 1)], unique=True)
        await self.breakdown.create_index([("shop_id", 1), ("date", 1)])
        await self.daily.create_index([("shop_id", 1), ("date", 1)], unique=True)
        await self.daily.create_index([("shop_id", 1), ("timestamp", -1)])

    async def process_event(self, payload: PurchaseAnalyticsSchema):
        def _extract_date(val) -> str:
            if not val:
                return datetime.utcnow().strftime("%Y-%m-%d")
            s = str(val).strip()
            if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                return s[:10]
            return datetime.utcnow().strftime("%Y-%m-%d")

        # Group incoming items by purchase_id
        purchases_map = {}
        for item in payload.datas:
            p_id = item.purchase_id or "UNKNOWN"
            if p_id not in purchases_map:
                purchases_map[p_id] = {
                    "purchase_id": p_id,
                    "supplier_id": item.supplier_id or "",
                    "stocks": 0.0,
                    "purchase_amounts": 0.0,
                    "outstanding_amounts": float(item.outstanding_amounts or 0.0),
                    "created_at": item.created_at,
                    "date": _extract_date(item.created_at)
                }
            purchases_map[p_id]["stocks"] += float(item.stocks or 0.0)
            purchases_map[p_id]["purchase_amounts"] += float(item.purchase_amounts or 0.0)
            if item.outstanding_amounts is not None and float(item.outstanding_amounts) > 0:
                purchases_map[p_id]["outstanding_amounts"] = float(item.outstanding_amounts)

            # Update metrics on product breakdown & supplier breakdown
            from .prod_inv_repo import prod_inv_repo
            await prod_inv_repo.apply_purchase(
                shop_id=payload.shop_id,
                product_id=item.product_id,
                variant_id=item.variant_id or "",
                batch_id=item.batch_id or "",
                stocks=item.stocks or 0.0,
                amount=item.purchase_amounts or 0.0,
                outstanding=item.outstanding_amounts or 0.0,
                total_purchase=1,
            )

            from .supplier_repo import supplier_repo
            await supplier_repo.apply_purchase(
                shop_id=payload.shop_id,
                supplier_id=item.supplier_id,
                amount=item.purchase_amounts or 0.0,
                total_purchase=1,
            )

        # Upsert each purchase in breakdown
        for p_id, p_data in purchases_map.items():
            await self.breakdown.update_one(
                {"shop_id": payload.shop_id, "purchase_id": p_id},
                {
                    "$set": {
                        "shop_id": payload.shop_id,
                        "purchase_id": p_id,
                        "supplier_id": p_data["supplier_id"],
                        "stocks": p_data["stocks"],
                        "purchase_amounts": p_data["purchase_amounts"],
                        "outstanding_amounts": p_data["outstanding_amounts"],
                        "date": p_data["date"],
                        "created_at": p_data["created_at"],
                        "timestamp": datetime.utcnow()
                    }
                },
                upsert=True
            )

        # Recalculate overall & daily from breakdown
        await self.recalculate_overall(payload.shop_id)
        await self.recalculate_daily(payload.shop_id)
        return {"success": True}

    async def recalculate_overall(self, shop_id: str):
        pipeline = [
            {"$match": {"shop_id": shop_id}},
            {
                "$group": {
                    "_id": "$shop_id",
                    "total_purchase": {"$sum": 1},
                    "total_purchase_amounts": {"$sum": "$purchase_amounts"},
                    "total_purchase_stocks": {"$sum": "$stocks"},
                    "total_outstanding_amounts": {"$sum": "$outstanding_amounts"}
                }
            }
        ]
        agg_res = await self.breakdown.aggregate(pipeline).to_list(1)
        if agg_res:
            tot = agg_res[0]
            await self.overall.update_one(
                {"shop_id": shop_id},
                {
                    "$set": {
                        "shop_id": shop_id,
                        "total_purchase": int(tot.get("total_purchase", 0)),
                        "total_purchase_amounts": float(tot.get("total_purchase_amounts", 0.0)),
                        "total_purchase_stocks": float(tot.get("total_purchase_stocks", 0.0)),
                        "total_outstanding_amounts": float(tot.get("total_outstanding_amounts", 0.0)),
                        "timestamp": datetime.utcnow(),
                    }
                },
                upsert=True
            )
        else:
            await self.overall.update_one(
                {"shop_id": shop_id},
                {
                    "$set": {
                        "shop_id": shop_id,
                        "total_purchase": 0,
                        "total_purchase_amounts": 0.0,
                        "total_purchase_stocks": 0.0,
                        "total_outstanding_amounts": 0.0,
                        "timestamp": datetime.utcnow(),
                    }
                },
                upsert=True
            )

    async def recalculate_daily(self, shop_id: str):
        pipeline = [
            {"$match": {"shop_id": shop_id}},
            {
                "$group": {
                    "_id": "$date",
                    "total_purchase": {"$sum": 1},
                    "total_purchase_amounts": {"$sum": "$purchase_amounts"},
                    "total_purchase_stocks": {"$sum": "$stocks"},
                    "total_outstanding_amounts": {"$sum": "$outstanding_amounts"},
                    "latest_timestamp": {"$max": "$timestamp"}
                }
            }
        ]
        daily_res = await self.breakdown.aggregate(pipeline).to_list(None)
        await self.daily.delete_many({"shop_id": shop_id})
        for d in daily_res:
            date_str = d["_id"] or datetime.utcnow().strftime("%Y-%m-%d")
            await self.daily.update_one(
                {"shop_id": shop_id, "date": date_str},
                {
                    "$set": {
                        "shop_id": shop_id,
                        "date": date_str,
                        "total_purchase": int(d.get("total_purchase", 0)),
                        "total_purchase_amounts": float(d.get("total_purchase_amounts", 0.0)),
                        "total_purchase_stocks": float(d.get("total_purchase_stocks", 0.0)),
                        "total_outstanding_amounts": float(d.get("total_outstanding_amounts", 0.0)),
                        "timestamp": d.get("latest_timestamp") or datetime.utcnow()
                    }
                },
                upsert=True
            )

    async def get_overall(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        supplier_id: Optional[str] = None,
    ):
        if not start_date and not end_date and not supplier_id:
            return await self.overall.find_one({"shop_id": shop_id}, {"_id": 0})

        match_filter = {"shop_id": shop_id}
        if supplier_id:
            match_filter["supplier_id"] = supplier_id
        if start_date or end_date:
            match_filter["timestamp"] = {}
            if start_date:
                match_filter["timestamp"]["$gte"] = start_date
            if end_date:
                match_filter["timestamp"]["$lte"] = end_date

        pipeline = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": "$shop_id",
                    "total_purchase": {"$sum": 1},
                    "total_purchase_amounts": {"$sum": "$purchase_amounts"},
                    "total_purchase_stocks": {"$sum": "$stocks"},
                    "total_outstanding_amounts": {"$sum": "$outstanding_amounts"},
                }
            }
        ]
        res = await self.breakdown.aggregate(pipeline).to_list(1)
        if res:
            res[0].pop("_id", None)
            res[0]["shop_id"] = shop_id
            return res[0]
        return {
            "shop_id": shop_id,
            "total_purchase": 0,
            "total_purchase_amounts": 0.0,
            "total_purchase_stocks": 0.0,
            "total_outstanding_amounts": 0.0,
        }

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
            sort=[("timestamp", -1)],
        )

    async def purchase_trend(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        supplier_id: Optional[str] = None,
    ):
        filters = {"shop_id": shop_id}
        if supplier_id:
            filters["supplier_id"] = supplier_id
        if start_date or end_date:
            filters["timestamp"] = {}
            if start_date:
                filters["timestamp"]["$gte"] = start_date
            if end_date:
                filters["timestamp"]["$lte"] = end_date

        if supplier_id:
            cursor = self.breakdown.aggregate([
                {"$match": filters},
                {
                    "$group": {
                        "_id": "$date",
                        "total_purchase": {"$sum": 1},
                        "total_purchase_amounts": {"$sum": "$purchase_amounts"},
                        "total_purchase_stocks": {"$sum": "$stocks"},
                        "total_outstanding_amounts": {"$sum": "$outstanding_amounts"},
                    }
                },
                {"$sort": {"_id": 1}},
            ])
        else:
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

    async def dashboard(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        supplier_id: Optional[str] = None,
    ):
        return {
            "overall": await self.get_overall(shop_id, start_date, end_date, supplier_id),
            "trend": await self.purchase_trend(shop_id, start_date, end_date, supplier_id),
        }

    async def delete_shop(self, shop_id: str):
        await self.overall.delete_one({"shop_id": shop_id})
        await self.breakdown.delete_many({"shop_id": shop_id})
        await self.daily.delete_many({"shop_id": shop_id})


purchase_repo = PurchaseRepo()
