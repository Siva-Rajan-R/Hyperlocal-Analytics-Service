
from typing import Union

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

    async def supplier_event(
        self,
        data: Union[SupplierAnalyticsSchema, dict],
    ):
        if isinstance(data, dict):
            data = SupplierAnalyticsSchema(**data)

        res = await supplier_repo.process_event(data)
        ic(res)
        return res

    async def customer_event(
        self,
        data: Union[CustomerAnalyticsSchema, dict],
    ):
        if isinstance(data, dict):
            data = CustomerAnalyticsSchema(**data)

        res = await customer_repo.process_event(data)
        ic(res)
        return res

    async def purchase_event(
        self,
        data: Union[PurchaseAnalyticsSchema, dict],
    ):
        if isinstance(data, dict):
            data = PurchaseAnalyticsSchema(**data)

        res = await purchase_repo.process_event(data)
        ic(res)
        return res

    async def prodinv_event(
        self,
        data: Union[ProdInvAnalyticsSchema, dict],
    ):
        if isinstance(data, dict):
            data = ProdInvAnalyticsSchema(**data)

        res = await prod_inv_repo.process_inventory_sync(data)
        ic(res)
        return res

    async def stockmovadj_event(
        self,
        data: Union[StockMovAdjAnalyticsSchema, dict],
    ):
        if isinstance(data, dict):
            data = StockMovAdjAnalyticsSchema(**data)

        res = await stockmovadj_repo.process_event(data)
        ic(res)
        return res

    async def sales_event(
        self,
        data: Union[SalesAnalyticsSchema, dict],
    ):
        if isinstance(data, dict):
            data = SalesAnalyticsSchema(**data)

        res = await sales_repo.process_event(data)
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
