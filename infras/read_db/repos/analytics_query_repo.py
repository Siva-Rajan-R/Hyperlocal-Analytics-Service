
import asyncio
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
        supplier_id: Optional[str] = None,
    ):
        (
            supplier,
            customer,
            purchase,
            inventory,
            stock_adj,
            sales,
        ) = await asyncio.gather(
            supplier_repo.dashboard(shop_id),
            customer_repo.dashboard(shop_id),
            purchase_repo.dashboard(shop_id, start_date=start_date, end_date=end_date, supplier_id=supplier_id),
            prod_inv_repo.dashboard(shop_id),
            stockmovadj_repo.dashboard(shop_id),
            sales_repo.dashboard(shop_id, start_date=start_date, end_date=end_date),
        )
        return {
            "supplier": supplier,
            "customer": customer,
            "purchase": purchase,
            "inventory": inventory,
            "stock_adjustment": stock_adj,
            "sales": sales,
        }

    async def overview(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        supplier_id: Optional[str] = None,
    ):
        (
            supplier,
            customer,
            purchase,
            inventory,
            stock_adj,
            sales,
        ) = await asyncio.gather(
            supplier_repo.get_overall(shop_id, supplier_id=supplier_id),
            customer_repo.get_overall(shop_id),
            purchase_repo.get_overall(shop_id, start_date=start_date, end_date=end_date, supplier_id=supplier_id),
            prod_inv_repo.get_overall(shop_id),
            stockmovadj_repo.get_overall(shop_id),
            sales_repo.get_overall(shop_id, start_date=start_date, end_date=end_date),
        )
        return {
            "supplier": supplier,
            "customer": customer,
            "purchase": purchase,
            "inventory": inventory,
            "stock_adjustment": stock_adj,
            "sales": sales,
        }

    async def top_entities(self, shop_id: str, limit: int = 10, supplier_id: Optional[str] = None):
        (
            top_suppliers,
            top_customers,
            top_products,
        ) = await asyncio.gather(
            supplier_repo.top_suppliers(shop_id, limit, supplier_id=supplier_id),
            customer_repo.top_customers(shop_id, limit),
            prod_inv_repo.top_products(shop_id, limit),
        )
        return {
            "top_suppliers": top_suppliers,
            "top_customers": top_customers,
            "top_products": top_products,
        }

    async def trends(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        supplier_id: Optional[str] = None,
    ):
        (
            suppliers,
            customers,
            purchases,
            stock_adjustments,
            sales,
        ) = await asyncio.gather(
            supplier_repo.supplier_trend(shop_id, start_date, end_date),
            customer_repo.customer_trend(shop_id, start_date, end_date),
            purchase_repo.purchase_trend(shop_id, start_date, end_date, supplier_id=supplier_id),
            stockmovadj_repo.trend(shop_id, start_date, end_date),
            sales_repo.sales_trend(shop_id, start_date, end_date),
        )
        return {
            "suppliers": suppliers,
            "customers": customers,
            "purchases": purchases,
            "stock_adjustments": stock_adjustments,
            "sales": sales,
        }

    async def inventory_health(self, shop_id: str):
        (
            overall,
            low_stock,
            out_of_stock,
        ) = await asyncio.gather(
            prod_inv_repo.get_overall(shop_id),
            prod_inv_repo.low_stock_products(shop_id),
            prod_inv_repo.out_of_stock_products(shop_id),
        )
        return {
            "overall": overall,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
        }

    async def full_report(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        supplier_id: Optional[str] = None,
        limit: int = 10,
    ):
        (
            overview,
            dashboard,
            top,
            trends,
            inventory,
        ) = await asyncio.gather(
            self.overview(shop_id, start_date, end_date, supplier_id),
            self.dashboard(shop_id, start_date, end_date, supplier_id),
            self.top_entities(shop_id, limit, supplier_id),
            self.trends(shop_id, start_date, end_date, supplier_id),
            self.inventory_health(shop_id),
        )
        return {
            "overview": overview,
            "dashboard": dashboard,
            "top": top,
            "trends": trends,
            "inventory": inventory,
        }

    async def unified_dashboard(
        self,
        shop_id: str,
        product_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        result = {}
        
        # Concurrently fetch specific entity details if requested
        entity_tasks = []
        entity_keys = []
        if product_id:
            entity_keys.append("product")
            entity_tasks.append(prod_inv_repo.get_product(shop_id, product_id))
        if supplier_id:
            entity_keys.append("supplier")
            entity_tasks.append(supplier_repo.get_supplier(shop_id, supplier_id))
        if customer_id:
            entity_keys.append("customer")
            entity_tasks.append(customer_repo.get_customer(shop_id, customer_id))
            
        if entity_tasks:
            entity_results = await asyncio.gather(*entity_tasks)
            for k, val in zip(entity_keys, entity_results):
                result[k] = val

        # Concurrently execute dashboard sections
        (
            overview,
            dashboard,
            trends,
            inventory,
            top,
        ) = await asyncio.gather(
            self.overview(shop_id, start_date, end_date, supplier_id),
            self.dashboard(shop_id, start_date, end_date, supplier_id),
            self.trends(shop_id, start_date, end_date, supplier_id),
            self.inventory_health(shop_id),
            self.top_entities(shop_id, 10, supplier_id),
        )
        
        result["overview"] = overview
        result["dashboard"] = dashboard
        result["trends"] = trends
        result["inventory"] = inventory
        result["top"] = top
            
        return result


analytics_query_repo = AnalyticsQueryRepo()
