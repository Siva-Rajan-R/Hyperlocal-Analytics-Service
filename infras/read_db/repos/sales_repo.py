from datetime import datetime
from typing import Optional

from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.sales_schemas.request_schemas import SalesAnalyticsSchema
from .analytics_base_repo import AnalyticsBaseRepo


class SalesRepo(AnalyticsBaseRepo):

    def __init__(self):
        super().__init__(ANALYTICS_COLLECTIONS["sales"]["overall"])
        self.overall = ANALYTICS_COLLECTIONS["sales"]["overall"]
        self.daily = ANALYTICS_COLLECTIONS["sales"]["daily"]

    async def create_indexes(self):
        await self.overall.create_index([("shop_id", 1)], unique=True)
        await self.daily.create_index([("shop_id", 1), ("date", 1)], unique=True)
        await self.daily.create_index([("shop_id", 1), ("timestamp", -1)])

    async def process_event(self, payload: SalesAnalyticsSchema):
        print(payload.model_dump())
        total_amount = 0.0
        total_stock = 0.0
        total_online_sales = 0
        total_online_sales_amount = 0.0
        total_offline_sales = 0
        total_offline_sales_amount = 0.0

        def _extract_date(val) -> str:
            if not val:
                return datetime.utcnow().strftime("%Y-%m-%d")
            s = str(val).strip()
            if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                return s[:10]
            return datetime.utcnow().strftime("%Y-%m-%d")

        unique_sales = len({item.sales_id for item in payload.datas if item.sales_id}) or len(payload.datas) or 1
        daily_groups = {}

        for item in payload.datas:
            total_amount += item.sales_amounts or 0
            total_stock += item.stocks or 0
            
            is_online = (item.sales_type or "").upper() == "ONLINE"
            if is_online:
                total_online_sales += 1
                total_online_sales_amount += item.sales_amounts or 0
            else:
                total_offline_sales += 1
                total_offline_sales_amount += item.sales_amounts or 0
            
            d = _extract_date(getattr(item, "created_at", None))
            if d not in daily_groups:
                daily_groups[d] = {
                    "sales_ids": set(),
                    "total_amount": 0.0,
                    "total_stock": 0.0,
                    "online_sales": 0,
                    "online_sales_amount": 0.0,
                    "offline_sales": 0,
                    "offline_sales_amount": 0.0,
                    "latest_created": getattr(item, "created_at", None)
                }
            if item.sales_id:
                daily_groups[d]["sales_ids"].add(item.sales_id)
            daily_groups[d]["total_amount"] += item.sales_amounts or 0
            daily_groups[d]["total_stock"] += item.stocks or 0
            if is_online:
                daily_groups[d]["online_sales"] += 1
                daily_groups[d]["online_sales_amount"] += item.sales_amounts or 0
            else:
                daily_groups[d]["offline_sales"] += 1
                daily_groups[d]["offline_sales_amount"] += item.sales_amounts or 0

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

        await self.overall.update_one(
            {"shop_id": payload.shop_id},
            {
                "$inc": {
                    "total_sales": unique_sales,
                    "total_sales_amounts": total_amount,
                    "total_sales_stocks": total_stock,
                    "total_online_sales": total_online_sales,
                    "total_online_sales_amount": total_online_sales_amount,
                    "total_offline_sales": total_offline_sales,
                    "total_offline_sales_amount": total_offline_sales_amount,
                },
                "$set": {
                    "shop_id": payload.shop_id,
                    "timestamp": datetime.utcnow(),
                },
            },
            upsert=True,
        )

        for d, stats in daily_groups.items():
            cnt = len(stats["sales_ids"]) or 1
            ts = stats["latest_created"] if stats["latest_created"] else datetime.utcnow()
            await self.daily.update_one(
                {
                    "shop_id": payload.shop_id,
                    "date": d,
                },
                {
                    "$inc": {
                        "total_sales": cnt,
                        "total_sales_amounts": stats["total_amount"],
                        "total_sales_stocks": stats["total_stock"],
                        "total_online_sales": stats["online_sales"],
                        "total_online_sales_amount": stats["online_sales_amount"],
                        "total_offline_sales": stats["offline_sales"],
                        "total_offline_sales_amount": stats["offline_sales_amount"],
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

    async def sales_trend(
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
                    "total_sales": {"$sum": "$total_sales"},
                    "total_sales_amounts": {"$sum": "$total_sales_amounts"},
                    "total_sales_stocks": {"$sum": "$total_sales_stocks"},
                    "total_online_sales": {"$sum": "$total_online_sales"},
                    "total_online_sales_amount": {"$sum": "$total_online_sales_amount"},
                    "total_offline_sales": {"$sum": "$total_offline_sales"},
                    "total_offline_sales_amount": {"$sum": "$total_offline_sales_amount"},
                }
            },
            {"$sort": {"_id": 1}},
        ])
        return await cursor.to_list(length=None)

    async def dashboard(self, shop_id: str):
        return {
            "overall": await self.get_overall(shop_id),
            "trend": await self.sales_trend(shop_id),
        }

    async def delete_shop(self, shop_id: str):
        await self.overall.delete_one({"shop_id": shop_id})
        await self.daily.delete_many({"shop_id": shop_id})


sales_repo = SalesRepo()
