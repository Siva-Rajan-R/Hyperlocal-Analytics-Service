from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from infras.read_db.repos.prod_inv_repo import ProdInvRepo
from schemas.v1.prodinv_schemas.request_schemas import ProdInvAnalyticsSchema


router = APIRouter(
    prefix="/prodinv",
    tags=["Product Inventory Analytics"],
)


# ---------------------------------------------------------
# WRITE
# ---------------------------------------------------------

@router.post("/event")
async def process_inventory_event(
    payload: ProdInvAnalyticsSchema,
):
    await ProdInvRepo().process_inventory_sync(payload)

    return {
        "success": True,
        "message": "Inventory analytics updated successfully.",
    }


# ---------------------------------------------------------
# READ
# ---------------------------------------------------------

@router.get("/overall")
async def get_inventory_overall(
    shop_id: str,
):
    return await ProdInvRepo().get_overall(shop_id)


@router.get("/")
async def list_products(
    shop_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    sales_type: Optional[str] = None,
):
    return await ProdInvRepo().list_products(
        shop_id=shop_id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        sales_type=sales_type,
    )


@router.get("/{product_id}")
async def get_product(
    shop_id: str,
    product_id: str,
):
    return await ProdInvRepo().get_product(
        shop_id=shop_id,
        product_id=product_id,
    )


@router.get("/{product_id}/variants/{variant_id}")
async def get_product_variant(
    shop_id: str,
    product_id: str,
    variant_id: str,
):
    return await ProdInvRepo().get_product_variant(
        shop_id=shop_id,
        product_id=product_id,
        variant_id=variant_id,
    )


@router.get("/{product_id}/variants/{variant_id}/batches/{batch_id}")
async def get_product_batch(
    shop_id: str,
    product_id: str,
    variant_id: str,
    batch_id: str,
):
    return await ProdInvRepo().get_product_batch(
        shop_id=shop_id,
        product_id=product_id,
        variant_id=variant_id,
        batch_id=batch_id,
    )

@router.get("/top")
async def top_products(
    shop_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    sales_type: Optional[str] = None,
):
    return await ProdInvRepo().top_products(
        shop_id=shop_id,
        limit=limit,
        sales_type=sales_type,
    )


@router.get("/low-stock")
async def low_stock_products(
    shop_id: str,
):
    return await ProdInvRepo().low_stock_products(shop_id)


@router.get("/out-of-stock")
async def out_of_stock_products(
    shop_id: str,
):
    return await ProdInvRepo().out_of_stock_products(shop_id)


@router.get("/dashboard")
async def inventory_dashboard(
    shop_id: str,
):
    return await ProdInvRepo().dashboard(shop_id)


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------

@router.delete("/shop/{shop_id}")
async def delete_inventory_analytics(
    shop_id: str,
):
    await ProdInvRepo().delete_shop(shop_id)

    return {
        "success": True,
        "message": "Inventory analytics deleted successfully.",
    }

