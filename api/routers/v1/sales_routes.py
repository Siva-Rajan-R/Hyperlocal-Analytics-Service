from datetime import datetime
from typing import Optional

from fastapi import APIRouter

from infras.read_db.repos.sales_repo import SalesRepo
from schemas.v1.sales_schemas.request_schemas import SalesAnalyticsSchema


router = APIRouter(
    prefix="/sales",
    tags=["Sales Analytics"],
)


# ---------------------------------------------------------
# WRITE
# ---------------------------------------------------------

@router.post("/event")
async def process_sales_event(
    payload: SalesAnalyticsSchema,
):
    await SalesRepo().process_event(payload)

    return {
        "success": True,
        "message": "Sales analytics updated successfully.",
    }


# ---------------------------------------------------------
# READ
# ---------------------------------------------------------

@router.get("/overall")
async def get_sales_overall(
    shop_id: str,
):
    return await SalesRepo().get_overall(shop_id)


@router.get("/daily")
async def get_daily_sales(
    shop_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    return await SalesRepo().get_daily(
        shop_id=shop_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/trend")
async def sales_trend(
    shop_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    return await SalesRepo().sales_trend(
        shop_id=shop_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/dashboard")
async def sales_dashboard(
    shop_id: str,
):
    return await SalesRepo().dashboard(shop_id)


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------

@router.delete("/shop/{shop_id}")
async def delete_sales_analytics(
    shop_id: str,
):
    await SalesRepo().delete_shop(shop_id)

    return {
        "success": True,
        "message": "Sales analytics deleted successfully.",
    }
