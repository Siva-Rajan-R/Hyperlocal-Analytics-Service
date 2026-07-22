
from datetime import datetime
from typing import Optional, Tuple

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

    @staticmethod
    def _stock_state(stock_value: float) -> Tuple[bool, float]:
        stock = max(float(stock_value or 0), 0.0)
        return stock > 0, 1.0 if stock <= 0 else 0.0

    @staticmethod
    def _overall_state_delta(previous_doc: Optional[dict], next_stock: float) -> dict:
        was_active = bool(previous_doc.get("is_active")) if previous_doc else False
        was_no_stock = float((previous_doc or {}).get("no_stocks") or 0) > 0
        is_active, next_no_stock = ProdInvRepo._stock_state(next_stock)
        is_no_stock = next_no_stock > 0

        delta = {}
        if was_active != is_active:
            delta["total_active_products"] = 1 if is_active else -1
            delta["total_inactive_product"] = -1 if is_active else 1
        if was_no_stock != is_no_stock:
            delta["total_no_stocks"] = 1 if is_no_stock else -1
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
        previous_stock = float((current or {}).get("stocks") or 0)
        next_stock = max(previous_stock + float(stock_delta or 0), 0.0)
        is_active, no_stock = self._stock_state(next_stock)
        overall_delta = self._overall_state_delta(current, next_stock) if count_overall_state else {}

        inc_fields = {"stocks": float(stock_delta or 0)}
        if extra_inc:
            inc_fields.update(extra_inc)

        set_fields = {
            "shop_id": shop_id,
            "product_id": product_id,
            "variant_id": variant_id or "",
            "batch_id": batch_id or "",
            "stocks": next_stock,
            "is_active": is_active,
            "no_stocks": no_stock,
            "timestamp": datetime.utcnow(),
        }
        if extra_set:
            set_fields.update(extra_set)

        update_doc = {
            "$set": set_fields,
            "$setOnInsert": {
                "low_stocks": 0,
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
                    "variant_id": item.variant_id or "",
                    "batch_id": item.batch_id or "",
                },
                {
                    "$set": {
                        "shop_id": payload.shop_id,
                        "product_id": item.product_id,
                        "variant_id": item.variant_id or "",
                        "batch_id": item.batch_id or "",
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
        return {"status": "success"}

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
        overall_delta = await self._apply_stock_state(
            shop_id=shop_id,
            product_id=product_id,
            variant_id=variant_id or "",
            batch_id=batch_id or "",
            stock_delta=stocks,
            extra_inc=purchase_inc,
            count_overall_state=(variant_id or "") == "" and (batch_id or "") == "",
        )

        if (variant_id or "") != "" or (batch_id or "") != "":
            product_delta = await self._apply_product_stock_state(
                shop_id=shop_id,
                product_id=product_id,
                stock_delta=stocks,
                extra_inc=purchase_inc,
            )
            overall_delta.update(product_delta)

        inc_fields = {"total_stocks": stocks}
        inc_fields.update(overall_delta)
        await self.overall.update_one(
            {"shop_id": shop_id},
            {
                "$inc": inc_fields,
                "$set": {"shop_id": shop_id, "timestamp": datetime.utcnow()},
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

        stock_delta = stocks if is_increment else -stocks
        extra_inc = {k: v for k, v in inc_fields.items() if k != "stocks"}
        overall_delta = await self._apply_stock_state(
            shop_id=shop_id,
            product_id=product_id,
            variant_id=variant_id or "",
            batch_id=batch_id or "",
            stock_delta=stock_delta,
            extra_inc=extra_inc,
            count_overall_state=(variant_id or "") == "" and (batch_id or "") == "",
        )

        if (variant_id or "") != "" or (batch_id or "") != "":
            product_delta = await self._apply_product_stock_state(
                shop_id=shop_id,
                product_id=product_id,
                stock_delta=stock_delta,
                extra_inc=extra_inc,
            )
            overall_delta.update(product_delta)

        inc_overall = {"total_stocks": stock_delta}
        inc_overall.update(overall_delta)
        await self.overall.update_one(
            {"shop_id": shop_id},
            {
                "$inc": inc_overall,
                "$set": {"shop_id": shop_id, "timestamp": datetime.utcnow()},
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

        extra_inc = {k: v for k, v in inc_fields.items() if k != "stocks"}
        overall_delta = await self._apply_stock_state(
            shop_id=shop_id,
            product_id=product_id,
            variant_id=variant_id or "",
            batch_id=batch_id or "",
            stock_delta=-stocks,
            extra_inc=extra_inc,
            count_overall_state=(variant_id or "") == "" and (batch_id or "") == "",
        )

        if (variant_id or "") != "" or (batch_id or "") != "":
            product_delta = await self._apply_product_stock_state(
                shop_id=shop_id,
                product_id=product_id,
                stock_delta=-stocks,
                extra_inc=extra_inc,
            )
            overall_delta.update(product_delta)

        inc_overall = {"total_stocks": -stocks}
        inc_overall.update(overall_delta)
        await self.overall.update_one(
            {"shop_id": shop_id},
            {
                "$inc": inc_overall,
                "$set": {"shop_id": shop_id, "timestamp": datetime.utcnow()},
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
            {"shop_id": shop_id, "low_stocks": {"$gt": 0}},
            {"_id": 0}
        ).sort("low_stocks", -1)
        return await cursor.to_list(length=None)

    async def out_of_stock_products(self, shop_id: str):
        cursor = self.breakdown.find(
            {"shop_id": shop_id, "no_stocks": {"$gt": 0}},
            {"_id": 0}
        ).sort("timestamp", -1)
        return await cursor.to_list(length=None)

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


