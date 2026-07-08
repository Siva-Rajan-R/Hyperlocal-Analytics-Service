from infras.read_db.models.prod_inv_model import (
    ProdInvReadModel,
    ProdInvReadModelCategoryInfosType,
    ProdInvReadModelUnitInfosType,
    ProdInvReadModelVariantInfosType,
    ProdInvReadModelSerialnoInfosType,
    ProdInvReadModelStockInfosType,
    ProdInvReadModelPricingInfosType,
    ProdInvReadModelStorageLocationInfosType,
    ProdInvReadModelReorderPointInfosType,
    ProdInvReadModelBatchInfosType,
    ProdInvReadModelTypeInfosType,
    ProdInvReadModelInventoryUnitsType
)
from typing import Dict, Any, List
from datetime import datetime
from icecream import ic

def get_field(obj, field_name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(field_name, default)
    return getattr(obj, field_name, default)

def map_to_inventory_read_model(product_dict: Dict[str, Any]) -> ProdInvReadModel:
    """
    Maps the dictionary returned by `get_products_by_id` into the 
    MongoDB `ProdInvReadModel` schema.
    """
    inventory_units_raw = product_dict.get("inventory_units", [])
    
    inventory_units: List[ProdInvReadModelInventoryUnitsType] = []
    
    for unit in inventory_units_raw:
        # Variant
        variant_infos = unit.get("variant_infos")
        variant_rm = None
        if variant_infos:
            variant_rm = ProdInvReadModelVariantInfosType(
                id=str(get_field(variant_infos, "id", "")),
                name=str(get_field(variant_infos, "name", ""))
            )
            
        # Serial numbers
        serialno_infos = unit.get("serialno_infos")
        serialno_rm = None
        if serialno_infos:
            serialno_rm = []
            for s in serialno_infos:
                serialno_rm.append(ProdInvReadModelSerialnoInfosType(
                    id=str(get_field(s, "id", "")),
                    name=str(get_field(s, "name", ""))
                ))
                
        # Batch
        batch_infos = unit.get("batch_infos")
        batch_rm = None
        if batch_infos:
            expiry = get_field(batch_infos, "expiry_data")
            if not expiry:
                expiry = get_field(batch_infos, "expiry_date")
            mfg = get_field(batch_infos, "manufacturing_date")
            
            # Use current date as fallback if missing because the model requires date
            exp_date = datetime.fromisoformat(str(expiry)).date() if expiry else datetime.now().date()
            mfg_date = datetime.fromisoformat(str(mfg)).date() if mfg else datetime.now().date()
                
            batch_rm = ProdInvReadModelBatchInfosType(
                id=str(get_field(batch_infos, "id", "")),
                name=str(get_field(batch_infos, "name", "")),
                expiry_data=exp_date,
                manufacturing_date=mfg_date
            )
            
        # Stock
        stock_infos = unit.get("stock_infos")
        ic(stock_infos)
        stock_rm = ProdInvReadModelStockInfosType(
            id=str(get_field(stock_infos, "id", "")),
            physical_stocks=float(get_field(stock_infos, "physical_stocks", 0.0)),
            reserved_stocks=float(get_field(stock_infos, "reserved_stocks", 0.0)),
            available_Stocks=float(get_field(stock_infos, "available_stocks", 0.0))
        )
        
        # Pricing
        pricing_infos = unit.get("pricing_infos")
        pricing_rm = ProdInvReadModelPricingInfosType(
            id=str(get_field(pricing_infos, "id", "")),
            buy_price=float(get_field(pricing_infos, "buy_price", 0.0)),
            sell_price=float(get_field(pricing_infos, "sell_price", 0.0))
        )
        
        # Storage Location - build_inventory_units returns a list for storage_location_infos
        storage_infos_list = unit.get("storage_location_infos", [])
        storage_rm = None
        if storage_infos_list and len(storage_infos_list) > 0:
            first_storage = storage_infos_list[0]
            storage_rm = ProdInvReadModelStorageLocationInfosType(
                id=str(get_field(first_storage, "id", "")),
                name=str(get_field(first_storage, "name", ""))
            )
            
        # Reorder Point
        reorder_point_infos = unit.get("reorder_point_infos")
        reorder_rm = ProdInvReadModelReorderPointInfosType(
            id=str(get_field(reorder_point_infos, "id", "")),
            reorder_point=float(get_field(reorder_point_infos, "reorder_point", 0.0))
        )
        
        inventory_units.append(ProdInvReadModelInventoryUnitsType(
            variant_infos=variant_rm,
            serialno_infos=serialno_rm,
            batch_infos=batch_rm,
            stock_infos=stock_rm,
            pricing_infos=pricing_rm,
            storage_location_infos=storage_rm,
            reorder_point_infos=reorder_rm
        ))
        
    type_infos_raw = product_dict.get("type_infos", {})
    type_infos = ProdInvReadModelTypeInfosType(
        have_variant=bool(get_field(type_infos_raw, "has_variant", False)),
        have_batch=bool(get_field(type_infos_raw, "has_batch", False)),
        have_serialno=bool(get_field(type_infos_raw, "has_serialno", False))
    )
    
    cat_infos_raw = product_dict.get("category_infos")
    cat_infos = ProdInvReadModelCategoryInfosType(
        id=str(get_field(cat_infos_raw, "id", product_dict.get("category_id", ""))),
        name=str(get_field(cat_infos_raw, "name", "Unknown"))
    )
    
    unit_infos_raw = product_dict.get("unit_infos")
    unit_infos = ProdInvReadModelUnitInfosType(
        id=str(get_field(unit_infos_raw, "id", product_dict.get("unit_id", ""))),
        name=str(get_field(unit_infos_raw, "name", "Unknown"))
    )
    
    created_raw = product_dict.get("created_at")
    updated_raw = product_dict.get("updated_at")

    ic(product_dict)
    
    return ProdInvReadModel(
        id=str(product_dict.get("id", "")),
        ui_id=str(product_dict.get("ui_id", "")),
        shop_id=str(product_dict.get("shop_id", "")),
        sku=str(product_dict.get("sku", "")),
        barcode=str(product_dict.get("barcode", "")),
        name=str(product_dict.get("name", "")),
        description=str(product_dict.get("description", "")),
        category_infos=cat_infos,
        unit_infos=unit_infos,
        inventory_units=inventory_units,
        type_infos=type_infos,
        is_active=bool(product_dict.get("is_active", False)),
        have_tracking=bool(product_dict.get("have_tracking", False)),
        gst=str(product_dict.get("gst", "0%")),
        custom_fields=product_dict.get("custom_fields", {}),
        created_at=datetime.fromisoformat(str(created_raw)) if created_raw else datetime.now(),
        updated_at=datetime.fromisoformat(str(updated_raw)) if updated_raw else datetime.now()
    )
