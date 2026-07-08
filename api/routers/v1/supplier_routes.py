from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from infras.read_db.repos.supplier_repo import SupplierRepo
from schemas.v1.supplier_schemas.request_schemas import SupplierAnalyticsSchema


router = APIRouter(
    prefix="/supplier",
    tags=["Supplier Analytics"],
)


# ---------------------------------------------------------
# WRITE
# ---------------------------------------------------------

@router.post("/event")
async def process_supplier_event(
    payload: SupplierAnalyticsSchema,
):
    await SupplierRepo().process_event(payload)

    return {
        "success": True,
        "message": "Supplier analytics updated successfully.",
    }


# ---------------------------------------------------------
# READ
# ---------------------------------------------------------

@router.get("/overall")
async def get_supplier_overall(
    shop_id: str,
):
    return await SupplierRepo().get_overall(shop_id)


@router.get("/{supplier_id}")
async def get_supplier(
    shop_id: str,
    supplier_id: str,
):
    return await SupplierRepo().get_supplier(
        shop_id=shop_id,
        supplier_id=supplier_id,
    )


@router.get("/")
async def list_suppliers(
    shop_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    return await SupplierRepo().list_suppliers(
        shop_id=shop_id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/top")
async def top_suppliers(
    shop_id: str,
    limit: int = Query(default=10, ge=1, le=100),
):
    return await SupplierRepo().top_suppliers(
        shop_id=shop_id,
        limit=limit,
    )


@router.get("/trend")
async def supplier_trend(
    shop_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    return await SupplierRepo().supplier_trend(
        shop_id=shop_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/dashboard")
async def supplier_dashboard(
    shop_id: str,
):
    return await SupplierRepo().dashboard(shop_id)


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------

@router.delete("/shop/{shop_id}")
async def delete_supplier_analytics(
    shop_id: str,
):
    await SupplierRepo().delete_shop(shop_id)

    return {
        "success": True,
        "message": "Supplier analytics deleted successfully.",
    }
