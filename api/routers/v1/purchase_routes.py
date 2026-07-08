
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from infras.read_db.repos.purchase_repo import PurchaseRepo
from schemas.v1.purchase_schemas.request_schemas import PurchaseAnalyticsSchema


router = APIRouter(
    prefix="/purchase",
    tags=["Purchase Analytics"],
)


# ---------------------------------------------------------
# WRITE
# ---------------------------------------------------------

@router.post("/event")
async def process_purchase_event(
    payload: PurchaseAnalyticsSchema,
):
    await PurchaseRepo().process_event(payload)

    return {
        "success": True,
        "message": "Purchase analytics updated successfully.",
    }


# ---------------------------------------------------------
# READ
# ---------------------------------------------------------

@router.get("/overall")
async def get_purchase_overall(
    shop_id: str,
):
    return await PurchaseRepo().get_overall(shop_id)


@router.get("/daily")
async def get_daily_purchases(
    shop_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    return await PurchaseRepo().get_daily(
        shop_id=shop_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/trend")
async def purchase_trend(
    shop_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    return await PurchaseRepo().purchase_trend(
        shop_id=shop_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/dashboard")
async def purchase_dashboard(
    shop_id: str,
):
    return await PurchaseRepo().dashboard(shop_id)


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------

@router.delete("/shop/{shop_id}")
async def delete_purchase_analytics(
    shop_id: str,
):
    await PurchaseRepo().delete_shop(shop_id)

    return {
        "success": True,
        "message": "Purchase analytics deleted successfully.",
    }
