from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from infras.read_db.repos.analytics_query_repo import analytics_query_repo


router = APIRouter(
    prefix="/analytics-dashboard",
    tags=["Unified Analytics Dashboard"],
)

@router.get("/")
async def get_unified_dashboard(
    shop_id: str,
    product_id: Optional[str] = None,
    supplier_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    return await analytics_query_repo.unified_dashboard(
        shop_id=shop_id,
        product_id=product_id,
        supplier_id=supplier_id,
        customer_id=customer_id,
        category=category,
        start_date=start_date,
        end_date=end_date,
    )

@router.get("/resync")
async def resync_shop(shop_id: str):
    from infras.read_db.repos.sync_service import SyncService
    await SyncService.sync_shop_data(shop_id)
    return {"status": "success", "message": f"Resynced {shop_id}"}
