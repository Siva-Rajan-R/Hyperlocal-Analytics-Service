
from typing import Union,Any,Optional

from icecream import ic

from infras.read_db.repos.supplier_repo import supplier_repo
from infras.read_db.repos.customer_repo import customer_repo
from infras.read_db.repos.purchase_repo import purchase_repo
from infras.read_db.repos.prod_inv_repo import prod_inv_repo
from infras.read_db.repos.stockmovadj_repo import stockmovadj_repo
from infras.read_db.repos.sales_repo import sales_repo
from infras.read_db.repos.analytics_query_repo import analytics_query_repo

from schemas.v1.supplier_schemas.request_schemas import SupplierAnalyticsSchema
from schemas.v1.customer_schemas.request_schemas import CustomerAnalyticsSchema
from schemas.v1.purchase_schemas.request_schemas import PurchaseAnalyticsSchema
from schemas.v1.prodinv_schemas.request_schemas import ProdInvAnalyticsSchema
from schemas.v1.stockmovadj_schemas.request_schemas import StockMovAdjAnalyticsSchema
from schemas.v1.sales_schemas.request_schemas import SalesAnalyticsSchema


class MessagingQueueAnalyticsService:

    # ---------------- WRITE ---------------- #

    async def _handle_event(self, data: Any, schema_cls, repo_func):
        from infras.read_db.repos.sync_service import SyncService
        if isinstance(data, dict):
            shop_id = data.get("shop_id")
            entity_name = str(data.get("entity_name") or "").upper()
            entity_id = data.get("entity_id")

            if "datas" in data:
                try:
                    parsed_data = schema_cls(**data)
                    return await repo_func(parsed_data)
                except Exception as e:
                    ic(f"Schema parsing exception, falling back to sync: {e}")

            if shop_id and entity_id:
                if entity_name in ("SUPPLIER", "SUPPLIER_EVENT"):
                    return await SyncService.sync_single_supplier(shop_id=shop_id, supplier_id=str(entity_id))
                elif entity_name in ("CUSTOMER", "CUSTOMER_EVENT"):
                    return await SyncService.sync_single_customer(shop_id=shop_id, customer_id=str(entity_id))
                elif entity_name in ("PRODUCT", "PRODINV", "PRODINV_EVENT"):
                    return await SyncService.sync_single_product(shop_id=shop_id, product_id=str(entity_id))
                elif entity_name in ("PURCHASE", "PURCHASE_EVENT"):
                    return await SyncService.sync_single_purchase(shop_id=shop_id, purchase_id=str(entity_id))
                elif entity_name in ("ORDER", "SALES", "SALES_EVENT"):
                    return await SyncService.sync_single_order(shop_id=shop_id, order_id=str(entity_id))
                elif entity_name in ("STOCK_MOVEMENT", "STOCKMOVADJ", "STOCKMOVADJ_EVENT"):
                    return await SyncService.sync_single_stockmovadj(shop_id=shop_id, stockmovadj_id=str(entity_id))

            if shop_id:
                return await SyncService.sync_shop_data(shop_id=shop_id)
        else:
            return await repo_func(data)

    async def supplier_event(
        self,
        data: Union[SupplierAnalyticsSchema, dict],
    ):
        res = await self._handle_event(data, SupplierAnalyticsSchema, supplier_repo.process_event)
        ic(res)
        return res

    async def customer_event(
        self,
        data: Union[CustomerAnalyticsSchema, dict],
    ):
        res = await self._handle_event(data, CustomerAnalyticsSchema, customer_repo.process_event)
        ic(res)
        return res

    async def purchase_event(
        self,
        data: Union[PurchaseAnalyticsSchema, dict],
    ):
        res = await self._handle_event(data, PurchaseAnalyticsSchema, purchase_repo.process_event)
        ic(res)
        return res

    async def prodinv_event(
        self,
        data: Union[ProdInvAnalyticsSchema, dict],
    ):
        res = await self._handle_event(data, ProdInvAnalyticsSchema, prod_inv_repo.process_inventory_sync)
        ic(res)
        return res

    async def stockmovadj_event(
        self,
        data: Union[StockMovAdjAnalyticsSchema, dict],
    ):
        res = await self._handle_event(data, StockMovAdjAnalyticsSchema, stockmovadj_repo.process_event)
        ic(res)
        return res

    async def sales_event(
        self,
        data: Union[SalesAnalyticsSchema, dict],
    ):
        res = await self._handle_event(data, SalesAnalyticsSchema, sales_repo.process_event)
        ic(res)
        return res

    # ---------------- READ ---------------- #

    async def supplier_dashboard(self, shop_id: str):
        return await supplier_repo.dashboard(shop_id)

    async def customer_dashboard(self, shop_id: str):
        return await customer_repo.dashboard(shop_id)

    async def purchase_dashboard(self, shop_id: str):
        return await purchase_repo.dashboard(shop_id)

    async def prodinv_dashboard(self, shop_id: str):
        return await prod_inv_repo.dashboard(shop_id)

    async def stockmovadj_dashboard(self, shop_id: str):
        return await stockmovadj_repo.dashboard(shop_id)

    async def sales_dashboard(self, shop_id: str):
        return await sales_repo.dashboard(shop_id)

    async def analytics_dashboard(self, shop_id: str):
        return await analytics_query_repo.dashboard(shop_id)

    async def analytics_overview(self, shop_id: str):
        return await analytics_query_repo.overview(shop_id)

    async def analytics_report(
        self,
        shop_id: str,
        start_date=None,
        end_date=None,
        limit: int = 10,
    ):
        return await analytics_query_repo.full_report(
            shop_id=shop_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )


messaging_queue_analytics_service = MessagingQueueAnalyticsService()
