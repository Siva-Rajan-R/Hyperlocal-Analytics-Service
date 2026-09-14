from datetime import datetime
from typing import Optional

from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.sales_schemas.request_schemas import SalesAnalyticsSchema
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


class SalesRepo(AnalyticsBaseRepo):

    def __init__(self):
        super().__init__(ANALYTICS_COLLECTIONS["sales"]["overall"])
        self.overall = ANALYTICS_COLLECTIONS["sales"]["overall"]
        self.breakdown = ANALYTICS_COLLECTIONS["sales"]["breakdown"]
        self.daily = ANALYTICS_COLLECTIONS["sales"]["daily"]

    async def create_indexes(self):
        await self.overall.create_index([("shop_id", 1)], unique=True)
        await self.breakdown.create_index([("shop_id", 1), ("sales_id", 1)], unique=True)
        await self.breakdown.create_index([("shop_id", 1), ("date", 1)])
        await self.daily.create_index([("shop_id", 1), ("date", 1)], unique=True)
        await self.daily.create_index([("shop_id", 1), ("timestamp", -1)])

    async def process_event(self, payload: SalesAnalyticsSchema):
        # Group incoming line items by sales_id
        sales_map = {}
        for item in payload.datas:
            s_id = item.sales_id or "UNKNOWN"
            if s_id not in sales_map:
                sales_map[s_id] = {
                    "sales_id": s_id,
                    "customer_id": item.customer_id,
                    "sales_amounts": 0.0,
                    "cost_amounts": 0.0,
                    "profit_amounts": 0.0,
                    "stocks": 0.0,
                    "sales_type": (item.sales_type or "OFFLINE").upper(),
                    "created_at": item.created_at,
                    "date": _extract_date_str(item.created_at)
                }

            item_sales_amt = float(item.sales_amounts or 0.0)
            item_cost_amt = float(getattr(item, "cost_amounts", 0.0) or 0.0)
            item_profit_amt = float(getattr(item, "profit_amounts", 0.0) or 0.0)
            if item_profit_amt == 0.0:
                item_profit_amt = item_sales_amt - item_cost_amt

            sales_map[s_id]["sales_amounts"] += item_sales_amt
            sales_map[s_id]["cost_amounts"] += item_cost_amt
            sales_map[s_id]["profit_amounts"] += item_profit_amt
            sales_map[s_id]["stocks"] += float(item.stocks or 0.0)

            # Update product inventory analytics
            from .prod_inv_repo import prod_inv_repo
            await prod_inv_repo.apply_sale(
                shop_id=payload.shop_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                batch_id=item.batch_id,
                stocks=item.stocks or 0.0,
                amount=item.sales_amounts or 0.0,
                sales_type=item.sales_type,
            )

            # Update customer analytics (if customer_id is provided)
            if item.customer_id:
                from .customer_repo import customer_repo
                await customer_repo.apply_sale(
                    shop_id=payload.shop_id,
                    customer_id=item.customer_id,
                    amount=item.sales_amounts or 0.0,
                    sales_type=item.sales_type,
                )

        # Upsert each order into breakdown collection (idempotent!)
        for s_id, s_data in sales_map.items():
            await self.breakdown.update_one(
                {"shop_id": payload.shop_id, "sales_id": s_id},
                {
                    "$set": {
                        "shop_id": payload.shop_id,
                        "sales_id": s_id,
                        "customer_id": s_data["customer_id"],
                        "sales_amounts": s_data["sales_amounts"],
                        "cost_amounts": s_data["cost_amounts"],
                        "profit_amounts": s_data["profit_amounts"],
                        "stocks": s_data["stocks"],
                        "sales_type": s_data["sales_type"],
                        "date": s_data["date"],
                        "created_at": s_data["created_at"],
                        "timestamp": _parse_datetime(s_data["created_at"]) if s_data.get("created_at") else datetime.utcnow()
                    }
                },
                upsert=True
            )

        # Recalculate overall and daily from breakdown
        await self.recalculate_overall(payload.shop_id)
        await self.recalculate_daily(payload.shop_id)
        return {"status": "success"}

    async def recalculate_overall(self, shop_id: str):
        pipeline = [
            {"$match": {"shop_id": shop_id}},
            {
                "$group": {
                    "_id": "$shop_id",
                    "total_sales": {"$sum": 1},
                    "total_sales_amounts": {"$sum": "$sales_amounts"},
                    "total_cost": {"$sum": "$cost_amounts"},
                    "total_profit": {"$sum": "$profit_amounts"},
                    "total_sales_stocks": {"$sum": "$stocks"},
                    "total_online_sales": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, 1, 0]}
                    },
                    "total_online_sales_amount": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                    "total_offline_sales": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, 1, 0]}
                    },
                    "total_offline_sales_amount": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    }
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
                        "total_sales": int(tot.get("total_sales", 0)),
                        "total_sales_amounts": float(tot.get("total_sales_amounts", 0.0)),
                        "total_cost": float(tot.get("total_cost", 0.0)),
                        "total_profit": float(tot.get("total_profit", 0.0)),
                        "total_sales_stocks": float(tot.get("total_sales_stocks", 0.0)),
                        "total_online_sales": int(tot.get("total_online_sales", 0)),
                        "total_online_sales_amount": float(tot.get("total_online_sales_amount", 0.0)),
                        "total_offline_sales": int(tot.get("total_offline_sales", 0)),
                        "total_offline_sales_amount": float(tot.get("total_offline_sales_amount", 0.0)),
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
                        "total_sales": 0,
                        "total_sales_amounts": 0.0,
                        "total_cost": 0.0,
                        "total_profit": 0.0,
                        "total_sales_stocks": 0.0,
                        "total_online_sales": 0,
                        "total_online_sales_amount": 0.0,
                        "total_offline_sales": 0,
                        "total_offline_sales_amount": 0.0,
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
                    "total_sales": {"$sum": 1},
                    "total_sales_amounts": {"$sum": "$sales_amounts"},
                    "total_cost": {"$sum": "$cost_amounts"},
                    "total_profit": {"$sum": "$profit_amounts"},
                    "total_sales_stocks": {"$sum": "$stocks"},
                    "total_online_sales": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, 1, 0]}
                    },
                    "total_online_sales_amount": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                    "total_offline_sales": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, 1, 0]}
                    },
                    "total_offline_sales_amount": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
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
                        "total_sales": int(d.get("total_sales", 0)),
                        "total_sales_amounts": float(d.get("total_sales_amounts", 0.0)),
                        "total_cost": float(d.get("total_cost", 0.0)),
                        "total_profit": float(d.get("total_profit", 0.0)),
                        "total_sales_stocks": float(d.get("total_sales_stocks", 0.0)),
                        "total_online_sales": int(d.get("total_online_sales", 0)),
                        "total_online_sales_amount": float(d.get("total_online_sales_amount", 0.0)),
                        "total_offline_sales": int(d.get("total_offline_sales", 0)),
                        "total_offline_sales_amount": float(d.get("total_offline_sales_amount", 0.0)),
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
    ):
        if not start_date and not end_date:
            return await self.overall.find_one({"shop_id": shop_id}, {"_id": 0})

        filters = {"shop_id": shop_id}
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = _extract_date_str(start_date)
            if end_date:
                date_filter["$lte"] = _extract_date_str(end_date)
            filters["date"] = date_filter

        cursor = self.breakdown.aggregate([
            {"$match": filters},
            {
                "$group": {
                    "_id": "$shop_id",
                    "total_sales": {"$sum": 1},
                    "total_sales_amounts": {"$sum": "$sales_amounts"},
                    "total_cost": {"$sum": "$cost_amounts"},
                    "total_profit": {"$sum": "$profit_amounts"},
                    "total_sales_stocks": {"$sum": "$stocks"},
                    "total_online_sales": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, 1, 0]}
                    },
                    "total_online_sales_amount": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                    "total_offline_sales": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, 1, 0]}
                    },
                    "total_offline_sales_amount": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                }
            }
        ])
        res = await cursor.to_list(1)
        if res:
            res[0].pop("_id", None)
            res[0]["shop_id"] = shop_id
            return res[0]
        return {
            "shop_id": shop_id,
            "total_sales": 0,
            "total_sales_amounts": 0.0,
            "total_cost": 0.0,
            "total_profit": 0.0,
            "total_sales_stocks": 0.0,
            "total_online_sales": 0,
            "total_online_sales_amount": 0.0,
            "total_offline_sales": 0,
            "total_offline_sales_amount": 0.0,
        }

    async def get_daily(
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

    async def sales_trend(
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

        cursor = self.breakdown.aggregate([
            {"$match": filters},
            {
                "$group": {
                    "_id": "$date",
                    "total_sales": {"$sum": 1},
                    "total_sales_amounts": {"$sum": "$sales_amounts"},
                    "total_cost": {"$sum": "$cost_amounts"},
                    "total_profit": {"$sum": "$profit_amounts"},
                    "total_sales_stocks": {"$sum": "$stocks"},
                    "total_online_sales": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, 1, 0]}
                    },
                    "total_online_sales_amount": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                    "total_offline_sales": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, 1, 0]}
                    },
                    "total_offline_sales_amount": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
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
    ):
        return {
            "overall": await self.get_overall(shop_id, start_date, end_date),
            "trend": await self.sales_trend(shop_id, start_date, end_date),
        }

    async def delete_shop(self, shop_id: str):
        await self.overall.delete_one({"shop_id": shop_id})
        await self.breakdown.delete_many({"shop_id": shop_id})
        await self.daily.delete_many({"shop_id": shop_id})


sales_repo = SalesRepo()
