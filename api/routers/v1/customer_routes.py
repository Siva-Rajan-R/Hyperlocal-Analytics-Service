from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from infras.read_db.repos.customer_repo import CustomerRepo
from schemas.v1.customer_schemas.request_schemas import CustomerAnalyticsSchema


router = APIRouter(
    prefix="/customer",
    tags=["Customer Analytics"],
)


# ---------------------------------------------------------
# WRITE
# ---------------------------------------------------------

@router.post("/event")
async def process_customer_event(
    payload: CustomerAnalyticsSchema,
):
    await CustomerRepo().process_event(payload)

    return {
        "success": True,
        "message": "Customer analytics updated successfully.",
    }


# ---------------------------------------------------------
# READ
# ---------------------------------------------------------

@router.get("/overall")
async def get_customer_overall(
    shop_id: str,
):
    return await CustomerRepo().get_overall(shop_id)


@router.get("/{customer_id}")
async def get_customer(
    shop_id: str,
    customer_id: str,
):
    return await CustomerRepo().get_customer(
        shop_id=shop_id,
        customer_id=customer_id,
    )


@router.get("/")
async def list_customers(
    shop_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    sales_type: Optional[str] = None,
):
    return await CustomerRepo().list_customers(
        shop_id=shop_id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        sales_type=sales_type,
    )


@router.get("/top")
async def top_customers(
    shop_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    sales_type: Optional[str] = None,
):
    return await CustomerRepo().top_customers(
        shop_id=shop_id,
        limit=limit,
        sales_type=sales_type,
    )


@router.get("/trend")
async def customer_trend(
    shop_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    return await CustomerRepo().customer_trend(
        shop_id=shop_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/dashboard")
async def customer_dashboard(
    shop_id: str,
):
    return await CustomerRepo().dashboard(shop_id)


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------

@router.delete("/shop/{shop_id}")
async def delete_customer_analytics(
    shop_id: str,
):
    await CustomerRepo().delete_shop(shop_id)

    return {
        "success": True,
        "message": "Customer analytics deleted successfully.",
    }

