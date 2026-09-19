from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from icecream import ic

from messaging.saga_producer import SagaProducer, SagaStateErrorTypDict, SagaStateExecutionTypDict, CreateSagaStateSchema
from infras.primary_db.repos.product_repo import ProductRepo
from infras.read_db.repos.prod_inv_repo import ProdInvReadDbRepo
from infras.primary_db.main import AsyncSession
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from hyperlocal_platform.core.enums.saga_state_enum import SagaStatusEnum, SagaStepsValueEnum
from schemas.v1.product_schemas.request_schemas import GetBulkProductsById


async def emit_stock_mov_adj(session: AsyncSession, data: List[dict]) -> bool:
    """
    Emits stock movement adjustments via Saga orchestrators safely.
    Handles combinations of Variants, Batches, and Serial Numbers smoothly.
    """
    print("Inside emit stock mov adj")
    # prod_repo_obj = ProductRepo(session=session)
    prod_repo_obj = ProdInvReadDbRepo

    validated_data: Dict[str, List[dict]] = {}
    product_ids = []
    shop_id: Optional[str] = None
    
    # STEP-1: Group incoming payload datasets by Product ID
    for prod in data:
        product_id = prod['product_id']
        shop_id = prod['shop_id']
        
        if product_id not in validated_data:
            validated_data[product_id] = []
        
        validated_data[product_id].append(prod)
        if product_id not in product_ids:
            product_ids.append(product_id)
            
    # STEP-2: Fetch matching inventory profiles from Primary DB
    # product_res = await prod_repo_obj.get_bulk_products_by_id(
    #     data=GetBulkProductsById(shop_id=shop_id, id=product_ids)
    # )
    product_res = await prod_repo_obj.get_bulk_by_id(
        data=GetBulkProductsById(shop_id=shop_id, id=product_ids)
    )
    # ic(product_res)
    
    stock_mov_adj_items = []
    adj_date = datetime.now()
    entity_name = "ADJUSTMENT"

    # STEP-3: Correlate payload adjustments against state profiles
    for prod_db in product_res:
        product_id = prod_db['id']
        product_name = prod_db['name']
        ui_id = prod_db['ui_id']
        category_infos=prod_db['category_infos']
        unit_infos=prod_db['unit_infos']
        
        type_infos = prod_db.get('type_infos', {})
        has_variant = type_infos.get('has_variant', False)
        has_batch = type_infos.get('has_batch', False)
        has_serialno = type_infos.get('has_serialno', False)

        strut_prod_res = validated_data.get(product_id)
        if not strut_prod_res:
            continue

        for val in strut_prod_res:
            batch_id = val.get('batch_id')
            variant_id = val.get('variant_id')
            update_type = val.get('type')
            entity_name = val.get('entity_name') or val.get('type_name') or entity_name
            stocks_adjusted = float(val.get('stocks', 0))

            variant_name = ""
            batch_infos = {}
            serialno_infos = []
            stock_infos = {}

            # --- Pathway A: Variant Target Strategy ---
            if has_variant:
                variants_dict = prod_db.get('variants', {})
                variant_data = variants_dict.get(variant_id) if variants_dict else None
                
                if not variant_data:
                    ic(f"Target variant {variant_id} mismatch for product {product_id}")
                    return False
                
                variant_name = variant_data.get('name', '')
                
                if has_batch:
                    batches_list = variant_data.get('batch_infos', [])
                    for batch in batches_list:
                        if batch.get('id') == batch_id:
                            batch_infos = batch
                            break
                    stock_infos = batch_infos.get('stock_infos', {})
                    serialno_infos = batch_infos.get('serialno_infos', []) if has_serialno else []
                else:
                    stock_infos = variant_data.get('stock_infos', {})
                    serialno_infos = variant_data.get('serialno_infos', []) if has_serialno else []

            # --- Pathway B: Standard Product Strategy ---
            else:
                if has_batch:
                    batches_list = prod_db.get('batch_infos', [])
                    for batch in batches_list:
                        if batch.get('id') == batch_id:
                            batch_infos = batch
                            break
                    stock_infos = batch_infos.get('stock_infos', {})
                    serialno_infos = batch_infos.get('serialno_infos', []) if has_serialno else []
                else:
                    stock_infos = prod_db.get('stock_infos', {})
                    serialno_infos = prod_db.get('serialno_infos', []) if has_serialno else []

            # Safely get current physical stocks metrics
            current_physical = float(stock_infos.get('physical_stocks', 0))

            # stock_before = physical stock BEFORE this adjustment
            # stock_after  = physical stock AFTER this adjustment
            if update_type == "INCREMENT":
                stock_before = current_physical - stocks_adjusted
                stock_after = current_physical
            else:
                stock_before = current_physical + stocks_adjusted
                stock_after = current_physical

            item_entity_name = val.get('entity_name') or val.get('type_name') or entity_name
            item_entity_id = (
                val.get('purchase_ui_id') or
                val.get('order_ui_id') or
                val.get('sale_ui_id') or
                val.get('return_ui_id') or
                val.get('exchange_ui_id') or
                val.get('sale_return_ui_id') or
                val.get('offline_sale_ui_id') or
                val.get('replacement_ui_id') or
                val.get('entity_id')
            )
            if not item_entity_id:
                for d in data:
                    if isinstance(d, dict):
                        item_entity_id = (
                            d.get('purchase_ui_id') or
                            d.get('order_ui_id') or
                            d.get('sale_ui_id') or
                            d.get('return_ui_id') or
                            d.get('exchange_ui_id') or
                            d.get('sale_return_ui_id') or
                            d.get('offline_sale_ui_id') or
                            d.get('replacement_ui_id') or
                            d.get('entity_id')
                        )
                        if item_entity_id:
                            break

            if item_entity_name == "OPENING_STOCK":
                item_desc = f"Opening stock initialized ({item_entity_id})" if item_entity_id else "Opening stock initialized"
            else:
                desc_entity = item_entity_name.replace("_", " ").lower() if item_entity_name else "adjustment"
                desc_entity = desc_entity.replace("offline ", "").replace("online ", "").strip()
                if update_type == "INCREMENT":
                    action_text = "Stock increase"
                elif update_type == "DECREMENT":
                    action_text = "Stock decrease"
                else:
                    action_text = "Stock adjusted"
                item_desc = f"{action_text} via {desc_entity} ({item_entity_id})" if item_entity_id else f"{action_text} via {desc_entity}"

            stock_mov_adj_items.append({
                'product_id': product_id,
                'name': product_name,
                'ui_id': ui_id,
                'category_id': category_id,
                'category_name': category_name,
                'unit_id': unit_id,
                'unit_name': unit_name,
                'variant_id': variant_id,
                'variant_name': variant_name,
                'batch_id': batch_infos.get('id') if batch_infos else None,
                'batch_name': batch_infos.get('name') if batch_infos else None,
                'exp_date': batch_infos.get('expiry_date') if batch_infos else None,
                'mfg_date': batch_infos.get('manufacturing_date') if batch_infos else None,
                'serial_numbers': [sn['name'] for sn in val.get('serial_numbers')] if val.get('serial_numbers') else None,
                'type': update_type,
                'entity_name': item_entity_name,
                'entity_id': item_entity_id,
                'order_ui_id': item_entity_id,
                'sale_ui_id': item_entity_id,
                'description': item_desc,
                'stocks_before': stock_before,
                'stocks_after': stock_after,
                'stocks': stocks_adjusted
            })

    entity_id_val = None
    if data:
        for d in data:
            if isinstance(d, dict):
                entity_id_val = (
                    d.get('purchase_ui_id') or
                    d.get('order_ui_id') or
                    d.get('sale_ui_id') or
                    d.get('return_ui_id') or
                    d.get('exchange_ui_id') or
                    d.get('sale_return_ui_id') or
                    d.get('offline_sale_ui_id') or
                    d.get('replacement_ui_id') or
                    d.get('entity_id') or
                    d.get('invoice_no')
                )
                if entity_id_val:
                    break

        if not entity_id_val:
            for d in data:
                if isinstance(d, dict):
                    entity_id_val = (
                        d.get('order_id') or
                        d.get('sale_id') or
                        d.get('return_id') or
                        d.get('purchase_id')
                    )
                    if entity_id_val:
                        break

    desc_entity = entity_name.replace("_", " ").lower().replace("offline ", "").strip() if entity_name else "adjustment"
    if entity_id_val:
        desc_str = f"Stock adjusted via {desc_entity} ({entity_id_val})"
    else:
        desc_str = f"Stock adjusted via {desc_entity}"

    mov_type = "PURCHASE" if entity_name == "PURCHASE_UPDATE" else entity_name

    # STEP-4: Package Transaction context for Saga Engine Orchestration
    stock_mov_adj_data = {
        'shop_id': shop_id,
        'type': mov_type,
        'date': adj_date.isoformat(),
        'description': desc_str,
        'entity_id': entity_id_val,
        'order_ui_id': entity_id_val,
        'sale_ui_id': entity_id_val,
        'entity_name': mov_type,
        'items': stock_mov_adj_items
    }

    ic(stock_mov_adj_data)

    saga_id = generate_uuid()
    await SagaProducer.emit(
        saga_payload=CreateSagaStateSchema(
            id=saga_id,
            status=SagaStatusEnum.PENDING,
            type="STOCK_ADJUSTMENT",
            data={'stock_mov_adj': stock_mov_adj_data},
            steps={
                'STOCK_ADJUSTMENT_CREATION': SagaStepsValueEnum.PENDING
            },
            execution={
                'step': 'STOCK_ADJUSTMENT_CREATION',
                'service': 'STOCK_MOV_ADJ'
            }
        ),
        headers={
            "entity_name": "create_adjustment",
            "reply_key": 'None',
            "reply_exchange": 'None',
            "reply_entity_name": 'None',
            "service_name": "STOCK_MOV_ADJ",
            "body": stock_mov_adj_data
        },
        routing_key="stockmovadj.service.routing.key",
        exchange_name="stockmovadj.service.exchange"
    )

    return True