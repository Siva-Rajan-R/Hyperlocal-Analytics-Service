from fastapi import APIRouter, Query
from infras.read_db.repos.sync_service import SyncService

router = APIRouter(
    prefix="/analytics-dashboard/sync",
    tags=["Analytics Sync"],
)

@router.post("")
async def sync_shop_data(shop_id: str = Query(...)):
    res = await SyncService.sync_shop_data(shop_id=shop_id)
    return {
        "success": True,
        "msg": "Analytics synchronization completed",
        "data": res
    }
