
from datetime import datetime
from typing import Optional

from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.supplier_schemas.request_schemas import SupplierAnalyticsSchema
from .analytics_base_repo import AnalyticsBaseRepo


def _parse_datetime(val) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        s = str(val).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


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
                    "total_outstanding_suppliers": {
                        "$sum": {
                            "$cond": [{"$gt": ["$total_outstandings", 0]}, 1, 0]
                        }
                    },
                    "outstanding_suppliers_count": {
                        "$sum": {
                            "$cond": [{"$gt": ["$total_outstandings", 0]}, 1, 0]
                        }
                    },
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
                        "total_outstanding_suppliers": int(tot.get("total_outstanding_suppliers", 0)),
                        "outstanding_suppliers_count": int(tot.get("outstanding_suppliers_count", 0)),
                        "timestamp": datetime.utcnow(),
                    }
                },
                upsert=True,
            )
        else:
            await self.overall.update_one(
                {"shop_id": payload.shop_id},
                {
                    "$set": {
                        "shop_id": payload.shop_id,
                        "total_suppliers": 0,
                        "total_outstandings": 0.0,
                        "total_cleared_amounts": 0.0,
                        "total_outstanding_suppliers": 0,
                        "outstanding_suppliers_count": 0,
                        "timestamp": datetime.utcnow(),
                    }
                },
                upsert=True,
            )
        return {"status": "success"}

    async def recalculate_supplier_purchases(self, shop_id: str, supplier_id: Optional[str] = None):
        purchase_breakdown = ANALYTICS_COLLECTIONS["purchase"]["breakdown"]
        match_filter: dict = {"shop_id": shop_id}
        if supplier_id:
            match_filter["supplier_id"] = supplier_id

        pipeline = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": "$supplier_id",
                    "total_purchases": {"$sum": 1},
                    "total_purchase_amounts": {"$sum": "$purchase_amounts"},
                    "total_purchase_stocks": {"$sum": "$stocks"}
                }
            }
        ]
        agg_results = await purchase_breakdown.aggregate(pipeline).to_list(None)

        updated_suppliers = set()
        for res in agg_results:
            s_id = res.get("_id")
            if not s_id:
                continue
            updated_suppliers.add(s_id)
            await self.breakdown.update_one(
                {"shop_id": shop_id, "supplier_id": s_id},
                {
                    "$set": {
                        "total_purchases": int(res.get("total_purchases", 0)),
                        "total_purchase_amounts": float(res.get("total_purchase_amounts", 0.0)),
                        "total_purchase_stocks": float(res.get("total_purchase_stocks", 0.0)),
                        "timestamp": datetime.utcnow()
                    }
                },
                upsert=True
            )

        if supplier_id and supplier_id not in updated_suppliers:
            await self.breakdown.update_one(
                {"shop_id": shop_id, "supplier_id": supplier_id},
                {
                    "$set": {
                        "total_purchases": 0,
                        "total_purchase_amounts": 0.0,
                        "total_purchase_stocks": 0.0,
                        "timestamp": datetime.utcnow()
                    }
                }
            )

    async def apply_purchase(
        self,
        shop_id: str,
        supplier_id: str,
        amount: float = 0.0,
        total_purchase: int = 1,
    ):
        if not supplier_id:
            return
        await self.recalculate_supplier_purchases(shop_id=shop_id, supplier_id=supplier_id)

    async def get_overall(self, shop_id: str, supplier_id: Optional[str] = None):
        if supplier_id:
            doc = await self.breakdown.find_one({"shop_id": shop_id, "supplier_id": supplier_id}, {"_id": 0})
            if doc:
                out_amt = float(doc.get("total_outstandings", 0.0))
                return {
                    "shop_id": shop_id,
                    "total_suppliers": 1,
                    "total_outstandings": out_amt,
                    "total_cleared_amounts": float(doc.get("total_cleared_amounts", 0.0)),
                    "total_outstanding_suppliers": 1 if out_amt > 0 else 0,
                    "outstanding_suppliers_count": 1 if out_amt > 0 else 0,
                }
            return {
                "shop_id": shop_id,
                "total_suppliers": 0,
                "total_outstandings": 0.0,
                "total_cleared_amounts": 0.0,
                "total_outstanding_suppliers": 0,
                "outstanding_suppliers_count": 0,
            }
        doc = await self.overall.find_one({"shop_id": shop_id}, {"_id": 0})
        if doc and "total_outstanding_suppliers" not in doc:
            out_count = await self.breakdown.count_documents({"shop_id": shop_id, "total_outstandings": {"$gt": 0}})
            doc["total_outstanding_suppliers"] = out_count
            doc["outstanding_suppliers_count"] = out_count
            await self.overall.update_one(
                {"shop_id": shop_id},
                {"$set": {"total_outstanding_suppliers": out_count, "outstanding_suppliers_count": out_count}}
            )
        return doc

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
        parsed_start = _parse_datetime(start_date)
        parsed_end = _parse_datetime(end_date)
        if parsed_start or parsed_end:
            filters["timestamp"] = {}
            if parsed_start:
                filters["timestamp"]["$gte"] = parsed_start
            if parsed_end:
                filters["timestamp"]["$lte"] = parsed_end

        return await self.paginate_query(
            filters=filters,
            page=page,
            page_size=page_size,
        )

    async def top_suppliers(self, shop_id: str, limit: int = 10, supplier_id: Optional[str] = None):
        filters: dict = {
            "shop_id": shop_id,
            "$or": [{"total_purchases": {"$gt": 0}}, {"total_purchase_amounts": {"$gt": 0}}]
        }
        if supplier_id:
            filters["supplier_id"] = supplier_id
        cursor = self.breakdown.find(
            filters,
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
        parsed_start = _parse_datetime(start_date)
        parsed_end = _parse_datetime(end_date)
        if parsed_start or parsed_end:
            filters["timestamp"] = {}
            if parsed_start:
                filters["timestamp"]["$gte"] = parsed_start
            if parsed_end:
                filters["timestamp"]["$lte"] = parsed_end

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
        top = await self.top_suppliers(shop_id, 3)
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
