
from datetime import datetime
from typing import Optional

from .supplier_repo import supplier_repo
from .customer_repo import customer_repo
from .purchase_repo import purchase_repo
from .prod_inv_repo import prod_inv_repo
from .stockmovadj_repo import stockmovadj_repo
from .sales_repo import sales_repo


class AnalyticsQueryRepo:

    async def dashboard(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        return {
            "supplier": await supplier_repo.dashboard(shop_id),
            "customer": await customer_repo.dashboard(shop_id),
            "purchase": await purchase_repo.dashboard(shop_id),
            "inventory": await prod_inv_repo.dashboard(shop_id),
            "stock_adjustment": await stockmovadj_repo.dashboard(shop_id),
            "sales": await sales_repo.dashboard(shop_id),
        }

    async def overview(self, shop_id: str):
        return {
            "supplier": await supplier_repo.get_overall(shop_id),
            "customer": await customer_repo.get_overall(shop_id),
            "purchase": await purchase_repo.get_overall(shop_id),
            "inventory": await prod_inv_repo.get_overall(shop_id),
            "stock_adjustment": await stockmovadj_repo.get_overall(shop_id),
            "sales": await sales_repo.get_overall(shop_id),
        }

    async def top_entities(self, shop_id: str, limit: int = 10):
        return {
            "top_suppliers": await supplier_repo.top_suppliers(shop_id, limit),
            "top_customers": await customer_repo.top_customers(shop_id, limit),
            "top_products": await prod_inv_repo.top_products(shop_id, limit),
        }

    async def trends(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        return {
            "suppliers": await supplier_repo.supplier_trend(
                shop_id, start_date, end_date
            ),
            "customers": await customer_repo.customer_trend(
                shop_id, start_date, end_date
            ),
            "purchases": await purchase_repo.purchase_trend(
                shop_id, start_date, end_date
            ),
            "stock_adjustments": await stockmovadj_repo.trend(
                shop_id, start_date, end_date
            ),
            "sales": await sales_repo.sales_trend(
                shop_id, start_date, end_date
            ),
        }

    async def inventory_health(self, shop_id: str):
        return {
            "overall": await prod_inv_repo.get_overall(shop_id),
            "low_stock": await prod_inv_repo.low_stock_products(shop_id),
            "out_of_stock": await prod_inv_repo.out_of_stock_products(shop_id),
        }

    async def full_report(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 10,
    ):
        return {
            "overview": await self.overview(shop_id),
            "dashboard": await self.dashboard(
                shop_id, start_date, end_date
            ),
            "top": await self.top_entities(shop_id, limit),
            "trends": await self.trends(
                shop_id, start_date, end_date
            ),
            "inventory": await self.inventory_health(shop_id),
        }
    async def unified_dashboard(
        self,
        shop_id: str,
        product_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        result = {}
        
        if product_id:
            result["product"] = await prod_inv_repo.get_product(shop_id, product_id)
        if supplier_id:
            result["supplier"] = await supplier_repo.get_supplier(shop_id, supplier_id)
        if customer_id:
            result["customer"] = await customer_repo.get_customer(shop_id, customer_id)
            
        result["overview"] = await self.overview(shop_id)
        result["dashboard"] = await self.dashboard(shop_id, start_date, end_date)
        result["trends"] = await self.trends(shop_id, start_date, end_date)
        result["inventory"] = await self.inventory_health(shop_id)
        result["top"] = await self.top_entities(shop_id)
            
        return result


analytics_query_repo = AnalyticsQueryRepo()
