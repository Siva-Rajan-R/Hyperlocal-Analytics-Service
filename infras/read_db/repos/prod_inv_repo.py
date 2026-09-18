
from datetime import datetime
from typing import Optional, Tuple,List

from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.prodinv_schemas.request_schemas import ProdInvAnalyticsSchema, ProdInvAnalyticsDatas
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

    @staticmethod
    def _stock_state(stock_value: float, rop_value: float = 0.0, is_active: bool = True, have_tracking: bool = True) -> Tuple[bool, float, float]:
        stock = max(float(stock_value or 0), 0.0)
        no_stock = 1.0 if (is_active and have_tracking and stock <= 0) else 0.0
        low_stock = 1.0 if (is_active and have_tracking and stock > 0 and rop_value > 0 and stock <= rop_value) else 0.0
        return is_active, no_stock, low_stock

    @staticmethod
    def _overall_state_delta(previous_doc: Optional[dict], next_stock: float, rop: float = 0.0) -> dict:
        if previous_doc and previous_doc.get("have_tracking") is False:
            return {}

        was_active = bool(previous_doc.get("is_active")) if previous_doc else False
        was_no_stock = float((previous_doc or {}).get("no_stocks") or 0) > 0
        was_low_stock = float((previous_doc or {}).get("low_stocks") or 0) > 0

        is_active = bool(previous_doc.get("is_active", True)) if previous_doc else True
        is_no_stock = is_active and next_stock <= 0
        is_low_stock = is_active and next_stock > 0 and rop > 0 and next_stock <= rop

        delta = {}
        if was_active != is_active:
            delta["total_active_products"] = 1 if is_active else -1
            delta["total_inactive_product"] = -1 if is_active else 1
        if was_no_stock != is_no_stock:
            delta["total_no_stocks"] = 1 if is_no_stock else -1
        if was_low_stock != is_low_stock:
            delta["total_low_stocks"] = 1 if is_low_stock else -1
        return delta

    async def _apply_stock_state(
        self,
        shop_id: str,
        product_id: str,
        variant_id: str,
        batch_id: str,
        stock_delta: float,
        extra_inc: Optional[dict] = None,
        extra_set: Optional[dict] = None,
        count_overall_state: bool = True,
    ):
        query = {
            "shop_id": shop_id,
            "product_id": product_id,
            "variant_id": variant_id or "",
            "batch_id": batch_id or "",
        }
        current = await self.breakdown.find_one(query, {"_id": 0})
        if current and current.get("have_tracking") is False:
            return {}

        previous_stock = float((current or {}).get("stocks") or 0)
        next_stock = max(previous_stock + float(stock_delta or 0), 0.0)
        rop = float((current or {}).get("reorder_point") or 0.0)
        is_active, no_stock, low_stock = self._stock_state(next_stock, rop)
        overall_delta = self._overall_state_delta(current, next_stock, rop) if count_overall_state else {}

        inc_fields = {"stocks": float(stock_delta or 0)}
        if extra_inc:
            inc_fields.update(extra_inc)

        set_fields = {
            "shop_id": shop_id,
            "product_id": product_id,
            "variant_id": variant_id or "",
            "batch_id": batch_id or "",
            "have_tracking": True,
            "stocks": next_stock,
            "is_active": is_active,
            "no_stocks": no_stock,
            "low_stocks": low_stock,
            "timestamp": datetime.utcnow(),
        }
        if extra_set:
            set_fields.update(extra_set)

        update_doc = {
            "$set": set_fields,
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
        }
        metric_inc_fields = {k: v for k, v in inc_fields.items() if k != "stocks"}
        if metric_inc_fields:
            update_doc["$inc"] = metric_inc_fields
            for k in metric_inc_fields:
                update_doc["$setOnInsert"].pop(k, None)

        await self.breakdown.update_one(
            query,
            update_doc,
            upsert=True,
        )

        return overall_delta

    async def _apply_product_stock_state(
        self,
        shop_id: str,
        product_id: str,
        stock_delta: float,
        extra_inc: Optional[dict] = None,
    ):
        return await self._apply_stock_state(
            shop_id=shop_id,
            product_id=product_id,
            variant_id="",
            batch_id="",
            stock_delta=stock_delta,
            extra_inc=extra_inc,
        )

    async def process_inventory_sync(self, payload: ProdInvAnalyticsSchema):
        active = inactive = non_tracking = 0
        total_stock = low_stock = no_stock = 0.0

        for item in payload.datas:
            if item.have_tracking is False:
                non_tracking += 1
                is_item_active = bool(item.is_active) if item.is_active is not None else True
                await self.breakdown.update_one(
                    {
                        "shop_id": payload.shop_id,
                        "product_id": item.product_id,
                        "variant_id": item.variant_id or "",
                        "batch_id": item.batch_id or "",
                    },
                    {
                        "$set": {
                            "shop_id": payload.shop_id,
                            "product_id": item.product_id,
                            "variant_id": item.variant_id or "",
                            "batch_id": item.batch_id or "",
                            "have_tracking": False,
                            "is_active": is_item_active,
                            "stocks": 0.0,
                            "low_stocks": 0.0,
                            "no_stocks": 0.0,
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
                continue

            # Trackable products:
            item_stocks = float(item.stocks or 0.0)
            is_item_active = bool(item.is_active) if item.is_active is not None else True
            if is_item_active:
                active += 1
            else:
                inactive += 1

            total_stock += item_stocks
            low_stock += float(item.low_stocks or 0.0)
            no_stock += float(item.no_stocks or 0.0)

            await self.breakdown.update_one(
                {
                    "shop_id": payload.shop_id,
                    "product_id": item.product_id,
                    "variant_id": item.variant_id or "",
                    "batch_id": item.batch_id or "",
                },
                {
                    "$set": {
                        "shop_id": payload.shop_id,
                        "product_id": item.product_id,
                        "variant_id": item.variant_id or "",
                        "batch_id": item.batch_id or "",
                        "have_tracking": True,
                        "is_active": is_item_active,
                        "stocks": item_stocks,
                        "low_stocks": float(item.low_stocks or 0.0),
                        "no_stocks": float(item.no_stocks or 0.0),
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

        await self.recalculate_overall(shop_id=payload.shop_id)
        return {"status": "success"}

    async def process_single_product_sync(self, shop_id: str, datas: List[ProdInvAnalyticsDatas]):
        for item in datas:
            if item.have_tracking is False:
                await self.breakdown.update_one(
                    {
                        "shop_id": shop_id,
                        "product_id": item.product_id,
                        "variant_id": item.variant_id or "",
                        "batch_id": item.batch_id or "",
                    },
                    {
                        "$set": {
                            "shop_id": shop_id,
                            "product_id": item.product_id,
                            "variant_id": item.variant_id or "",
                            "batch_id": item.batch_id or "",
                            "have_tracking": False,
                            "is_active": False,
                            "stocks": 0.0,
                            "low_stocks": 0.0,
                            "no_stocks": 0.0,
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
            else:
                item_stocks = float(item.stocks or 0.0)
                await self.breakdown.update_one(
                    {
                        "shop_id": shop_id,
                        "product_id": item.product_id,
                        "variant_id": item.variant_id or "",
                        "batch_id": item.batch_id or "",
                    },
                    {
                        "$set": {
                            "shop_id": shop_id,
                            "product_id": item.product_id,
                            "variant_id": item.variant_id or "",
                            "batch_id": item.batch_id or "",
                            "have_tracking": True,
                            "is_active": item_stocks > 0,
                            "stocks": item_stocks,
                            "low_stocks": float(item.low_stocks or 0.0),
                            "no_stocks": float(item.no_stocks or 0.0),
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

        await self.recalculate_overall(shop_id=shop_id)
        return {"status": "success"}

    async def recalculate_overall(self, shop_id: str):
        cursor = self.breakdown.find({"shop_id": shop_id})
        items = await cursor.to_list(length=None)

        products_map = {}
        for doc in items:
            pid = doc.get("product_id")
            if not pid:
                continue
            if pid not in products_map:
                products_map[pid] = []
            products_map[pid].append(doc)

        active = inactive = non_tracking = 0
        total_stock = low_stock = no_stock = 0.0

        for pid, units in products_map.items():
            is_non_tracking = any(u.get("have_tracking") is False for u in units)
            is_prod_active = any(bool(u.get("is_active", False)) for u in units)

            if is_non_tracking:
                non_tracking += 1
                continue

            prod_stock = sum(float(u.get("stocks") or 0.0) for u in units)
            total_stock += prod_stock

            if is_prod_active:
                active += 1
                # Actual out of stock count: is_active == True AND stock == 0
                if prod_stock <= 0:
                    no_stock += 1
                else:
                    prod_low_stock = sum(float(u.get("low_stocks") or 0.0) for u in units)
                    if prod_low_stock > 0:
                        low_stock += 1
            else:
                inactive += 1

        await self.overall.update_one(
            {"shop_id": shop_id},
            {
                "$set": {
                    "shop_id": shop_id,
                    "total_active_products": active,
                    "total_inactive_product": inactive,
                    "total_stocks": total_stock,
                    "total_low_stocks": low_stock,
                    "total_no_stocks": no_stock,
                    "total_non_tracking_products": non_tracking,
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
        total_purchase: int = 1,
    ):
        purchase_inc = {
            "total_purchases": total_purchase,
            "total_purchase_amounts": amount,
            "total_purchase_outstanding_amounts": outstanding,
        }
        await self.breakdown.update_one(
            {
                "shop_id": shop_id,
                "product_id": product_id,
                "variant_id": variant_id or "",
                "batch_id": batch_id or "",
            },
            {
                "$inc": purchase_inc,
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
        else:
            inc_fields["total_stockmovadj_decrements"] = stocks

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
        
        inc_fields = {}
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

    async def get_overall(self, shop_id: str):
        doc = await self.overall.find_one({"shop_id": shop_id}, {"_id": 0})
        if doc and "total_non_tracking_products" not in doc:
            doc["total_non_tracking_products"] = 0
        return doc

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
                "variant_id": "",
                "batch_id": "",
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
        pipeline = [
            {"$match": {"shop_id": shop_id, "variant_id": "", "batch_id": ""}},
            {
                "$addFields": {
                    "total_sales_amounts": {
                        "$add": [
                            {"$ifNull": ["$total_online_sales_amount", 0]},
                            {"$ifNull": ["$total_offline_sales_amount", 0]}
                        ]
                    },
                    "total_sales_stocks": {
                        "$add": [
                            {"$ifNull": ["$total_online_sales", 0]},
                            {"$ifNull": ["$total_offline_sales", 0]}
                        ]
                    }
                }
            },
            {"$sort": {"total_sales_amounts": -1}},
            {"$limit": limit},
            {"$project": {"_id": 0}},
        ]
        cursor = self.breakdown.aggregate(pipeline)
        return await cursor.to_list(length=None)

    async def low_stock_products(self, shop_id: str):
        cursor = self.breakdown.find(
            {"shop_id": shop_id, "low_stocks": {"$gt": 0}, "have_tracking": {"$ne": False}},
            {"_id": 0}
        ).sort("low_stocks", -1)
        return await cursor.to_list(length=None)

    async def out_of_stock_products(self, shop_id: str):
        cursor = self.breakdown.find(
            {"shop_id": shop_id, "is_active": True, "no_stocks": {"$gt": 0}, "have_tracking": {"$ne": False}},
            {"_id": 0}
        ).sort("timestamp", -1)
        return await cursor.to_list(length=None)

    async def dashboard(self, shop_id: str):
        return {
            "overall": await self.get_overall(shop_id),
            "top_products": await self.top_products(shop_id, 3),
            "low_stock": await self.low_stock_products(shop_id),
            "out_of_stock": await self.out_of_stock_products(shop_id),
        }

    async def delete_product(self, shop_id: str, product_id: str):
        await self.breakdown.delete_many({"shop_id": shop_id, "product_id": product_id})
        await self.recalculate_overall(shop_id=shop_id)
        return {"status": "success"}

    async def delete_shop(self, shop_id: str):
        await self.overall.delete_one({"shop_id": shop_id})
        await self.breakdown.delete_many({"shop_id": shop_id})


prod_inv_repo = ProdInvRepo()


