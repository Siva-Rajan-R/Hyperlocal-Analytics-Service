from datetime import datetime
from typing import Optional

from fastapi import APIRouter

from infras.read_db.repos.stockmovadj_repo import StockMovAdjRepo
from schemas.v1.stockmovadj_schemas.request_schemas import (
    StockMovAdjAnalyticsSchema,
)


router = APIRouter(
    prefix="/stockmovadj",
    tags=["Stock Movement Analytics"],
)


# ---------------------------------------------------------
# WRITE
# ---------------------------------------------------------

@router.post("/event")
async def process_stock_adjustment_event(
    payload: StockMovAdjAnalyticsSchema,
):
    await StockMovAdjRepo().process_event(payload)

    return {
        "success": True,
        "message": "Stock movement analytics updated successfully.",
    }


# ---------------------------------------------------------
# READ
# ---------------------------------------------------------

@router.get("/overall")
async def get_stock_adjustment_overall(
    shop_id: str,
):
    return await StockMovAdjRepo().get_overall(shop_id)


@router.get("/daily")
async def get_daily_stock_adjustments(
    shop_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    return await StockMovAdjRepo().daily_history(
        shop_id=shop_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/trend")
async def stock_adjustment_trend(
    shop_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    return await StockMovAdjRepo().trend(
        shop_id=shop_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/dashboard")
async def stock_adjustment_dashboard(
    shop_id: str,
):
    return await StockMovAdjRepo().dashboard(shop_id)


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------

@router.delete("/shop/{shop_id}")
async def delete_stock_adjustment_analytics(
    shop_id: str,
):
    await StockMovAdjRepo().delete_shop(shop_id)

    return {
        "success": True,
        "message": "Stock movement analytics deleted successfully.",
    }
