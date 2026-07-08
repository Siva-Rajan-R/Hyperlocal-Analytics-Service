from models.repo_models.base_repo_model import BaseRepoModel
from models.service_models.base_service_model import BaseServiceModel
from ..models.inventory_model import InventoryPricings,InventoryStocks,InventoryStoragelocations,InventoryReorderPoint
from ..models.product_model import ProductBatches,Products,ProductSerialNumbers,ProductVariants
# from ..models.product_model import Products,ProductBatches,ProductSerialNumbers,ProductVariants
# from ..models.inventory_model import InventoryPricings,InventoryStocks,InventoryStoragelocations
from ..repos.inventory_repo import InventoryRepo
from ..repos.product_repo import ProductRepo
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select,update,delete,func,or_,and_,String,case,cast,Text,literal,literal_column,text,bindparam,null
from sqlalchemy.dialects.postgresql import JSONB,ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction
from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from schemas.v1.prod_inv_schemas.request_schemas import CreateProdInvSchema,UpdateProdInvSchema,DeleteProdInvSchema,CreateUpdateInvAll,UpdateAllProdInvSchema,CreateProdInvBatchSerialnoSchema
from schemas.v1.product_schemas.request_schemas import GetAllProductSchema,GetBulkProductsById,GetProductsById,GetProductsByShopId,CreateProductBatchSchema,CreateProductSchema,CreateProductSerialnoSchema,CreateProductVariantSchema
from schemas.v1.product_schemas.db_schemas import CreateProductDbSchema,UpdateProductDbSchema,DeleteProductDbSchema,CreateProductBatchDbSchema,CreateProductSerialnoDbSchema
from schemas.v1.inventory_schemas.db_schemas import UpdateInventoryPricingDbSchema,UpdateInventoryReorderPointDbSchema,UpdateInventoryStockDbSchema,UpdateInventoryStorageLocationDbSchema,CreateInventoryPricingDbSchema,CreateInventoryReorderPointDbSchema,CreateInventoryStockDbSchema,CreateInventoryStorageLocationDbSchema
from typing import Optional,List,Dict,Any
from icecream import ic
from core.data_formats.enums.product_enums import ProductSerialnoStatusEnums
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from integrations.utility_service import get_ui_id,get_shop_unit,get_shop_category
from ...read_db.repos.prod_inv_repo import ProdInvReadDbRepo
from helpers.emit_stock_mov_adj import emit_stock_mov_adj
from ..services.customfield_service import CustomFieldsService
from schemas.v1.request_schemas.customfield_schema import CreateCustomFieldSchema,UpdateCustomFieldSchema,UpdateCustomFieldValueSchema,CreateCustomFieldValueSchema,BulkCreateCustomFieldValuesSchema

class ProductInventoryService:
    def __init__(self,session:AsyncSession):
        self.session=session

    async def create(self,data:CreateProdInvSchema):
        variants_toadd=[]
        storage_location_toadd=[]
        pricing_toadd=[]
        rop_toadd=[]

        product_id=generate_uuid()
        if data.type_infos.has_variant:
            for variant in data.variant_infos:
                variant_id=generate_uuid()
                variants_toadd.append(
                    ProductVariants(
                        id=variant_id,
                        sku=generate_uuid(),
                        product_id=product_id,
                        shop_id=data.shop_id,
                        name=variant.name
                    )
                )

                buy_price=None
                sell_price=None
                if not data.have_tracking:
                    buy_price=variant.buy_price
                    sell_price=variant.sell_price

                if buy_price and sell_price:
                    inv_pricing_id=generate_uuid()
                    pricing_toadd.append(
                        InventoryPricings(
                            id=inv_pricing_id,
                            product_id=product_id,
                            shop_id=data.shop_id,
                            variant_id=variant_id,
                            buy_price=buy_price,
                            sell_price=sell_price
                        )
                    )

                stl=None

                if variant.storage_location:
                    stl=variant.storage_location
                

                if stl:
                    inv_stl_id=generate_uuid()
                    storage_location_toadd.append(
                        InventoryStoragelocations(
                            id=inv_stl_id,
                            product_id=product_id,
                            shop_id=data.shop_id,
                            variant_id=variant_id,
                            name=stl
                        )
                    )
                
                rop=5
                if variant.reorder_point:
                    rop=variant.reorder_point

                rop_id=generate_uuid()
                rop_toadd.append(
                    InventoryReorderPoint(
                        id=rop_id,
                        product_id=product_id,
                        shop_id=data.shop_id,
                        variant_id=variant_id,
                        reorder_point=rop
                    )
                )

            
        else:
            
            buy_price=None
            sell_price=None

            if not data.have_tracking:
                buy_price=data.buy_price
                sell_price=data.sell_price

            if buy_price and sell_price:
                inv_pricing_id=generate_uuid()
                pricing_toadd.append(
                    InventoryPricings(
                        id=inv_pricing_id,
                        product_id=product_id,
                        shop_id=data.shop_id,
                        buy_price=buy_price,
                        sell_price=sell_price
                    )
                )


            stl=data.storage_location or None
            if stl:
                inv_stl_id=generate_uuid()
                storage_location_toadd.append(
                    InventoryStoragelocations(
                        id=inv_stl_id,
                        product_id=product_id,
                        shop_id=data.shop_id,
                        name=stl
                    )
                )
            
            rop=data.reorder_point or 5
            rop_id=generate_uuid()
            rop_toadd.append(
                InventoryReorderPoint(
                    id=rop_id,
                    product_id=product_id,
                    shop_id=data.shop_id,
                    variant_id=None,
                    reorder_point=rop
                )
            )

        ui_id_res=await get_ui_id(shop_id=data.shop_id)
        ic(ui_id_res)
        ui_id=f"{ui_id_res.get("prefix")}-{ui_id_res.get("current_number")}"
        ic(ui_id)
        product_toadd=CreateProductDbSchema(
            id=product_id,
            ui_id=ui_id,
            is_active=False,
            sku=generate_uuid(),
            **data.model_dump(exclude=["stocks","variant_infos","storage_location","buy_price","sell_price"])
        )

        product_repo_obj=ProductRepo(session=self.session)
        product_add_res=await product_repo_obj.create_product(data=product_toadd)
        variant_res=None
        if product_add_res and data.type_infos.has_variant and variants_toadd:
            variant_res=await product_repo_obj.create_bulk_variant(data=variants_toadd)
            ic(variant_res)
        
        if product_add_res:
            inv_repo_obj=InventoryRepo(session=self.session)
            cust_field_obj=CustomFieldsService(session=self.session)

            await inv_repo_obj.create_bulk_pricing(data=pricing_toadd)
            await inv_repo_obj.create_bulk_storage_location(data=storage_location_toadd)
            await inv_repo_obj.create_bulk_reorder_point(data=rop_toadd)

            if data.custom_fields and data.custom_fields.get("values"):
                ic("Inside Custom fields", data.custom_fields)
                cust_field_res = await cust_field_obj.bulk_upsert_values(
                    data=BulkCreateCustomFieldValuesSchema(
                        shop_id=data.shop_id,
                        product_id=product_id,
                        values=data.custom_fields.get("values")
                    )
                )

                ic(cust_field_res)
            
            try:
                from messaging.main import RabbitMQMessagingConfig
                rabbitmq_msg_obj = RabbitMQMessagingConfig()
                await rabbitmq_msg_obj.publish_event(
                    routing_key="activity_logs.routing.key",
                    exchange_name="activity_logs.exchange",
                    payload={
                        "shop_id": data.shop_id,
                        "user_name": "siva",
                        "service": "Inventory",
                        "action": "CREATE",
                        "entity_type": "Product",
                        "entity_id": product_id,
                        "description": f"Created new product '{data.name}' with {len(data.variant_infos) if data.type_infos.has_variant else 0} variant(s)",
                        "changes": [
                            {"field": "name", "before": "", "after": data.name},
                            {"field": "variants", "before": "", "after": str(len(data.variant_infos) if data.type_infos.has_variant else 0)}
                        ]
                    },
                    headers={}
                )
                
            except Exception as e:
                ic(f"Failed to publish activity log: {e}")
                
            # Sync to Read DB
            try:
                read_db_res=await ProdInvReadDbRepo.add_updatereaddb(
                    shop_id=data.shop_id,
                    product_ids=[product_id],
                    session=self.session
                )
                ic(read_db_res)
            except Exception as e:
                ic(f"Error syncing to read DB on create: {e}")
        

        return product_add_res
    

    async def update(self,data:UpdateProdInvSchema):
        product_repo_obj=ProductRepo(session=self.session)
        variants_toadd=[]
        variants_toupdate=[]
        storage_location_toupdate=[]
        storage_location_toadd=[]
        pricing_toupdate=[]
        pricing_toadd=[]
        rop_toadd=[]
        rop_toupdate=[]

        prod_get_res=await product_repo_obj.get_products_by_id(data=GetProductsById(shop_id=data.shop_id,id=data.id))
        if not prod_get_res:
            ic("The give product doesn't exists")
            return False
        
        if prod_get_res['is_active'] and not prod_get_res['have_tracking'] and data.have_tracking:
            ic("This product have a purchase, so you can't be able to make it as a normal one")
            return False

        if prod_get_res['is_active'] and not prod_get_res['type_infos']['has_variant'] and data.type_infos.has_variant:
            ic("This product have a purchase, so you can't be able to make create a variant")

        if prod_get_res['is_active'] and not prod_get_res['type_infos']['has_batch'] and data.type_infos.has_variant:
            ic("This product have a purchase, so you can't be able to make create a batch")
        
        if prod_get_res['is_active'] and not prod_get_res['type_infos']['has_serialno'] and data.type_infos.has_variant:
            ic("This product have a purchase, so you can't be able to make create a serialno")
        
        if data.type_infos.has_variant:
            for variant in data.variant_infos:
                if not variant.id:
                    variant_id=generate_uuid()
                    variants_toadd.append(
                        ProductVariants(
                            id=variant_id,
                            product_id=data.id,
                            shop_id=data.shop_id,
                            name=variant.name
                        )
                    )

                    if data.have_tracking:
                        inv_pricing_id=generate_uuid()
                        pricing_toadd.append(
                            InventoryPricings(
                                id=inv_pricing_id,
                                product_id=data.id,
                                shop_id=data.shop_id,
                                variant_id=variant_id,
                                buy_price=variant.buy_price,
                                sell_price=variant.sell_price
                            )
                        )

                    if variant.storage_location:
                        inv_stl_id=generate_uuid()
                        storage_location_toadd.append(
                            InventoryStoragelocations(
                                id=inv_stl_id,
                                product_id=data.id,
                                shop_id=data.shop_id,
                                variant_id=variant_id,
                                name=variant.storage_location
                            )
                        )
                    
                    if variant.reorder_point:
                        rop_id=generate_uuid()
                        rop_toadd.append(
                            InventoryReorderPoint(
                                id=rop_id,
                                product_id=data.id,
                                shop_id=data.shop_id,
                                variant_id=variant_id,
                                reorder_point=variant.reorder_point
                            )
                        )
                else:
                    variant_id=variant.id
                    variants_toupdate.append(
                        ProductVariants(
                            id=variant_id,
                            product_id=data.id,
                            shop_id=data.shop_id,
                            name=variant.name
                        )
                    )

                    if data.have_tracking:
                        inv_pricing_id=variant.pricing_id
                        pricing_toupdate.append(
                            InventoryPricings(
                                id=inv_pricing_id,
                                product_id=data.id,
                                shop_id=data.shop_id,
                                variant_id=variant_id,
                                buy_price=variant.buy_price,
                                sell_price=variant.sell_price
                            )
                        )

                    if variant.storage_location:
                        inv_stl_id=variant.storage_location_id
                        if not inv_stl_id:
                            inv_stl_id=generate_uuid()
                            storage_location_toadd.append(
                                InventoryStoragelocations(
                                    id=inv_stl_id,
                                    product_id=data.id,
                                    shop_id=data.shop_id,
                                    variant_id=variant_id,
                                    name=variant.storage_location
                                )
                            )
                        else:
                            storage_location_toupdate.append(
                                UpdateInventoryStorageLocationDbSchema(
                                    id=inv_stl_id,
                                    product_id=data.id,
                                    shop_id=data.shop_id,
                                    name=variant.storage_location
                                )
                            )

                    if variant.reorder_point:
                        rop_id=variant.reorder_point_id
                        if not rop_id:
                            rop_id=generate_uuid()
                            rop_toadd.append(
                                InventoryReorderPoint(
                                    id=rop_id,
                                    product_id=data.id,
                                    shop_id=data.shop_id,
                                    variant_id=variant_id,
                                    reorder_point=variant.reorder_point
                                )
                            )
                        else:
                            rop_toupdate.append(
                                UpdateInventoryReorderPointDbSchema(
                                    id=rop_id,
                                    product_id=data.id,
                                    shop_id=data.shop_id,
                                    reorder_point=variant.reorder_point
                                )
                            )
            
        else:
            if data.have_tracking:
                inv_pricing_id=data.pricing_id
                if not inv_pricing_id:
                    inv_pricing_id=generate_uuid()
                    pricing_toadd.append(
                        InventoryPricings(
                            id=inv_pricing_id,
                            product_id=data.id,
                            shop_id=data.shop_id,
                            buy_price=data.buy_price,
                            sell_price=data.sell_price
                        )
                    )
                else:
                    pricing_toupdate.append(
                        UpdateInventoryPricingDbSchema(
                            id=inv_pricing_id,
                            product_id=data.id,
                            shop_id=data.shop_id,
                            buy_price=data.buy_price,
                            sell_price=data.sell_price
                        )
                    )

            if data.storage_location:
                inv_stl_id=data.storage_location_id
                if not inv_stl_id:
                    inv_stl_id=generate_uuid()
                    storage_location_toadd.append(
                        InventoryStoragelocations(
                            id=inv_stl_id,
                            product_id=data.id,
                            shop_id=data.shop_id,
                            name=data.storage_location
                        )
                    )
                else:
                    storage_location_toupdate.append(
                        UpdateInventoryStorageLocationDbSchema(
                            id=inv_stl_id,
                            product_id=data.id,
                            shop_id=data.shop_id,
                            name=data.storage_location
                        )
                    ) 

            if data.reorder_point:
                rop_id=data.reorder_point_id
                if not rop_id:
                    rop_id=generate_uuid()
                    rop_toadd.append(
                        InventoryReorderPoint(
                            id=rop_id,
                            product_id=data.id,
                            shop_id=data.shop_id,
                            reorder_point=data.reorder_point
                        )
                    )
                else:
                    rop_toupdate.append(
                        UpdateInventoryReorderPointDbSchema(
                            id=rop_id,
                            product_id=data.id,
                            shop_id=data.shop_id,
                            reorder_point=data.reorder_point
                        )
                    )

        
        product_toadd=UpdateProductDbSchema(
            id=data.id,
            **data.model_dump(exclude=["stocks","variant_infos","storage_location","buy_price","sell_price","id"])
        )

        ic(product_toadd,variants_toadd,variants_toupdate,pricing_toadd,pricing_toupdate,storage_location_toadd,storage_location_toupdate)
        
        product_add_res=await product_repo_obj.update_bulk_product(data=[product_toadd])
        ic(product_add_res)
        if product_add_res and data.type_infos.has_variant:
            if variants_toadd:
                variant_res=await product_repo_obj.create_bulk_variant(data=variants_toadd)
            else:
                variant_res=await product_repo_obj.update_bulk_variant(data=variants_toupdate)
            ic(variant_res)
        
        if product_add_res:
            inv_repo_obj=InventoryRepo(session=self.session)

            await inv_repo_obj.create_bulk_pricing(data=pricing_toadd)
            await inv_repo_obj.create_bulk_storage_location(data=storage_location_toadd)
            await inv_repo_obj.create_bulk_reorder_point(data=rop_toadd)

            await inv_repo_obj.update_bulk_pricing(data=pricing_toupdate)
            await inv_repo_obj.update_bulk_storage_location(data=storage_location_toupdate)
            await inv_repo_obj.update_bulk_reorder_point(data=rop_toupdate)
            
            if data.custom_fields and data.custom_fields.get("values"):
                cust_field_obj = CustomFieldsService(session=self.session)
                await cust_field_obj.bulk_upsert_values(
                    data=BulkCreateCustomFieldValuesSchema(
                        shop_id=data.shop_id,
                        product_id=data.id,
                        values=data.custom_fields.get("values")
                    )
                )
            
            changes_list = ActivityLogger.compute_changes(prod_get_res, data.model_dump(mode='json', exclude_none=True, exclude_unset=True))
            if changes_list:
                desc_changes = [f"{c['field']} prv({c['before']}) after ({c['after']})" for c in changes_list]
                desc = f"updated product {', '.join(desc_changes)}"
                try:
                    from messaging.main import RabbitMQMessagingConfig
                    rabbitmq_msg_obj = RabbitMQMessagingConfig()
                    await rabbitmq_msg_obj.publish_event(
                        routing_key="activity_logs.routing.key",
                        exchange_name="activity_logs.exchange",
                        payload={
                            "shop_id": data.shop_id,
                            "user_name": "siva",
                            "service": "Inventory",
                            "action": "UPDATE",
                            "entity_type": "ProductInventory",
                            "entity_id": data.id,
                            "description": desc,
                            "changes": changes_list
                        },
                        headers={}
                    )
                except Exception as e:
                    ic(f"Failed to publish activity log: {e}")

            # Sync to Read DB
            try:
                from schemas.v1.product_schemas.request_schemas import GetProductsById
                prod_get_res_updated = await product_repo_obj.get_products_by_id(data=GetProductsById(id=data.id, shop_id=data.shop_id, include_serialno=True))
                if prod_get_res_updated:
                    prod_dict = prod_get_res_updated[0] if isinstance(prod_get_res_updated, list) else prod_get_res_updated
                    
                    from integrations.utility_service import get_shop_category, get_shop_unit
                    
                    # Fetch category
                    cat_id = prod_dict.get("category_id")
                    if cat_id:
                        cat_data = await get_shop_category(shop_id=data.shop_id, category_id=cat_id)
                        if cat_data:
                            prod_dict["category_infos"] = cat_data
                            
                    # Fetch unit
                    unit_id = prod_dict.get("unit_id")
                    if unit_id:
                        unit_data = await get_shop_unit(shop_id=data.shop_id, unit_id=unit_id)
                        if unit_data:
                            prod_dict["unit_infos"] = unit_data

                    from core.utils.read_db_mapper import map_to_inventory_read_model
                    from infras.read_db.repos.supplier_repo import InventoryReadDbRepo
                    
                    # Fetch Custom Fields
                    from infras.primary_db.services.customfield_service import CustomFieldsService
                    cf_service = CustomFieldsService(session=self.session)
                    try:
                        cf_values = await cf_service.get_values_by_product(product_id=data.id, shop_id=data.shop_id)
                        prod_dict["custom_fields"] = {v["field_name"]: v["value"] for v in cf_values} if cf_values else {}
                    except Exception as e:
                        ic(f"Error fetching custom fields for read db on update: {e}")
                        prod_dict["custom_fields"] = {}

                    read_model = map_to_inventory_read_model(prod_dict)
                    await InventoryReadDbRepo.replace_inventory(read_model)
            except Exception as e:
                ic(f"Error syncing to read DB on update: {e}")
        
        return True
    

    async def create_bulk_batch(self,data:List[CreateProductBatchSchema]):
        batch_toadd=[]
        for batch in data:
            batch_id:str=generate_uuid()
            batch_toadd.append(
                CreateProductBatchDbSchema(
                    id=batch_id,
                    **batch.model_dump(mode="json")
                )
            )
        res=await ProductRepo(session=self.session).create_bulk_batch(data=batch_toadd)
        ic(res)
        return res
    

    async def create_bulk_serialno(self,data:List[CreateProductSerialnoSchema]):
        serialno_toadd=[]
        for serialno in data:
            serialno_id:str=generate_uuid()
            serialno_toadd.append(
                CreateProductSerialnoDbSchema(
                    id=serialno_id,
                    **serialno.model_dump(mode="json")
                )
            )
        res=await ProductRepo(session=self.session).create_bulk_selialno(data=serialno_toadd)
        ic(res)
        return res
    

    async def delete(self,data:DeleteProdInvSchema):
        product_del_data=DeleteProductDbSchema(id=data.id,shop_id=data.shop_id)
        res=await ProductRepo(session=self.session).delete_product(data=product_del_data)
        ic(res)
        if res:
            try:
                from messaging.main import RabbitMQMessagingConfig
                rabbitmq_msg_obj = RabbitMQMessagingConfig()
                await rabbitmq_msg_obj.publish_event(
                    routing_key="activity_logs.routing.key",
                    exchange_name="activity_logs.exchange",
                    payload={
                        "shop_id": data.shop_id,
                        "user_name": "siva",
                        "service": "Inventory",
                        "action": "DELETE",
                        "entity_type": "ProductInventory",
                        "entity_id": data.id,
                        "description": f"Deleted product {data.id}",
                        "changes": [{"field": "id", "before": str(data.id), "after": "DELETED"}]
                    },
                    headers={}
                )
            except Exception as e:
                ic(f"Failed to publish activity log: {e}")
                
            # Sync to Read DB
            try:
                from infras.read_db.repos.supplier_repo import InventoryReadDbRepo
                await InventoryReadDbRepo.delete_inventory(inventory_id=data.id, shop_id=data.shop_id)
            except Exception as e:
                ic(f"Error syncing to read DB on delete: {e}")
                
        return res
    

    async def create_batch_serialno(self,data:List[CreateProdInvBatchSerialnoSchema]):
        batch_toadd=[]
        serialno_toadd=[]

        batch_res=[]
        serialno_res=[]

        for batch_serial in data:
            batch_id=generate_uuid()
            batch=CreateProductBatchDbSchema(
                id=batch_id,
                shop_id=batch_serial.shop_id,
                variant_id=batch_serial.variant_id,
                product_id=batch_serial.product_id,
                name=batch_serial.batch_infos.name,
                expiration_infos=batch_serial.batch_infos.expiration_infos.model_dump(mode="json"),
            )
            batch_toadd.append(ProductBatches(**batch.model_dump(mode="json")))
            batch_res.append(batch.model_dump(mode="json"))

            for serialno in batch_serial.serial_numbers:
                serialno=CreateProductSerialnoDbSchema(
                    id=generate_uuid(),
                    shop_id=batch_serial.shop_id,
                    variant_id=batch_serial.variant_id,
                    product_id=batch_serial.product_id,
                    batch_id=batch_id,
                    name=serialno,
                    status=ProductSerialnoStatusEnums.AVAILABLE.value
                )
                serialno_toadd.append(ProductSerialNumbers(**serialno.model_dump(mode="json")))
                serialno_res.append(serialno.model_dump(mode="json"))
        
        await ProductRepo(session=self.session).create_bulk_batch(data=batch_toadd)
        await ProductRepo(session=self.session).create_bulk_selialno(data=serialno_toadd)


        return {
            "batches":batch_res,
            "serialnos":serialno_res
        }


    async def create_update_inventory_all(self,data:CreateUpdateInvAll):
        gst_toupdate=[]
        gst_added_prod_id=[]
        stock_toadd=[]
        stock_toupdate=[]

        stl_toadd=[]
        stl_toupdate=[]

        rop_toadd=[]
        rop_toupdate=[]

        pricing_toadd=[]
        pricing_toupdate=[]

        for create_data in data.create:
            if create_data.gst and create_data.gst not in gst_added_prod_id:
                gst_toupdate.append(
                    UpdateProductDbSchema(
                        id=create_data.product_id,
                        shop_id=create_data.shop_id,
                        gst=create_data.gst
                    )
                )
            if create_data.stocks_infos:
                stock_toadd.append(
                    InventoryStocks(
                        id=generate_uuid(),
                        shop_id=create_data.shop_id,
                        product_id=create_data.product_id,
                        variant_id=create_data.variant_id,
                        batch_id=create_data.batch_id,
                        physical_stocks=create_data.stocks_infos.physical_stocks,
                        reserved_stocks=create_data.stocks_infos.reserved_stocks or 0,
                        available_stocks=create_data.stocks_infos.physical_stocks
                    )
                )

            if create_data.pricing_infos:
                pricing_toadd.append(
                    InventoryPricings(
                        id=generate_uuid(),
                        shop_id=create_data.shop_id,
                        product_id=create_data.product_id,
                        variant_id=create_data.variant_id,
                        batch_id=create_data.batch_id,
                        buy_price=create_data.pricing_infos.buy_price,
                        sell_price=create_data.pricing_infos.sell_price

                    )
                )
            
            if create_data.storage_location_infos:
                stl_toadd.append(
                    InventoryStoragelocations(
                        id=generate_uuid(),
                        shop_id=create_data.shop_id,
                        product_id=create_data.product_id,
                        variant_id=create_data.variant_id,
                        batch_id=create_data.batch_id,
                        name=create_data.storage_location_infos.name
                    )
                )

            if create_data.reorder_point_infos:
                rop_toadd.append(
                    InventoryReorderPoint(
                        id=generate_uuid(),
                        shop_id=create_data.shop_id,
                        product_id=create_data.product_id,
                        variant_id=create_data.variant_id,
                        batch_id=create_data.batch_id,
                        reorder_point=create_data.reorder_point_infos.reorder_point
                    )
                )

        for update_data in data.update:
            if create_data.gst and create_data.gst not in gst_added_prod_id:
                gst_toupdate.append(
                    UpdateProductDbSchema(
                        id=create_data.product_id,
                        shop_id=create_data.shop_id,
                        gst=create_data.gst
                    )
                )
            if update_data.stocks_infos:
                stock_toupdate.append(
                    UpdateInventoryStockDbSchema(
                        id=update_data.stocks_infos.id,
                        shop_id=update_data.shop_id,
                        product_id=update_data.product_id,
                        variant_id=update_data.variant_id,
                        batch_id=update_data.batch_id,
                        type=getattr(update_data.stocks_infos, 'type', 'DIRECT'),
                        physical_stocks=update_data.stocks_infos.physical_stocks,
                        reserved_stocks=update_data.stocks_infos.reserved_stocks or 0,
                    )
                )

            if update_data.pricing_infos:
                pricing_toupdate.append(
                    UpdateInventoryPricingDbSchema(
                        id=update_data.pricing_infos.id,
                        shop_id=update_data.shop_id,
                        product_id=update_data.product_id,
                        variant_id=update_data.variant_id,
                        batch_id=update_data.batch_id,
                        buy_price=update_data.pricing_infos.buy_price,
                        sell_price=update_data.pricing_infos.sell_price

                    )
                )
            
            if update_data.storage_location_infos:
                stl_toupdate.append(
                    UpdateInventoryStorageLocationDbSchema(
                        id=update_data.storage_location_infos.id,
                        shop_id=update_data.shop_id,
                        product_id=update_data.product_id,
                        variant_id=update_data.variant_id,
                        batch_id=update_data.batch_id,
                        name=update_data.storage_location_infos.name
                    )
                )

            if update_data.reorder_point_infos:
                rop_toupdate.append(
                    UpdateInventoryReorderPointDbSchema(
                        id=update_data.reorder_point_infos.id,
                        shop_id=update_data.shop_id,
                        product_id=update_data.product_id,
                        variant_id=update_data.variant_id,
                        batch_id=update_data.batch_id,
                        reorder_point=update_data.reorder_point_infos.reorder_point
                    )
                )

        inv_repo_obj=InventoryRepo(session=self.session)
        prod_repo_obj=ProductRepo(session=self.session)
        await inv_repo_obj.create_bulk_stocks(data=stock_toadd)
        await inv_repo_obj.create_bulk_pricing(data=pricing_toadd)
        await inv_repo_obj.create_bulk_reorder_point(data=rop_toadd)
        await inv_repo_obj.create_bulk_storage_location(data=stl_toadd)

        await inv_repo_obj.update_bulk_stocks(data=stock_toupdate)
        await inv_repo_obj.update_bulk_pricing(data=pricing_toupdate)
        await inv_repo_obj.update_bulk_reorder_point(data=rop_toupdate)
        await inv_repo_obj.update_bulk_storage_location(data=stl_toupdate)

        await prod_repo_obj.update_bulk_product(data=gst_toupdate)
        
        shop_id = None
        if data.create:
            shop_id = data.create[0].shop_id
        elif data.update:
            shop_id = data.update[0].shop_id
            
        if shop_id:
            try:
                from messaging.main import RabbitMQMessagingConfig
                rabbitmq_msg_obj = RabbitMQMessagingConfig()
                await rabbitmq_msg_obj.publish_event(
                    routing_key="activity_logs.routing.key",
                    exchange_name="activity_logs.exchange",
                    payload={
                        "shop_id": shop_id,
                        "user_name": "siva",
                        "service": "Inventory",
                        "action": "UPDATE",
                        "entity_type": "InventoryBulk",
                        "entity_id": "bulk",
                        "description": f"Bulk created/updated inventory items",
                        "changes": [{"field": "bulk_operation", "before": "N/A", "after": "COMPLETED"}]
                    },
                    headers={}
                )
            except Exception as e:
                ic(f"Failed to publish activity log: {e}")
                
            # Sync to Read DB
            try:
                product_ids = set()
                if data.create:
                    for item in data.create: product_ids.add(item.product_id)
                if data.update:
                    for item in data.update: product_ids.add(item.product_id)
                    
                if product_ids:
                    from schemas.v1.product_schemas.request_schemas import GetBulkProductsById
                    bulk_get = await ProductRepo(session=self.session).get_bulk_products_by_id(
                        data=GetBulkProductsById(id=list(product_ids), shop_id=shop_id, include_serialno=True)
                    )
                    from core.utils.read_db_mapper import map_to_inventory_read_model
                    from infras.read_db.repos.supplier_repo import InventoryReadDbRepo
                    from integrations.utility_service import get_shop_category, get_shop_unit
                    
                    # Cache to avoid repetitive HTTP calls for same category/unit
                    category_cache = {}
                    unit_cache = {}

                    for prod_res in bulk_get:
                        prod_dict = prod_res
                        
                        # Fetch Category
                        cat_id = prod_dict.get("category_id")
                        if cat_id:
                            if cat_id not in category_cache:
                                category_cache[cat_id] = await get_shop_category(shop_id=shop_id, category_id=cat_id)
                            if category_cache[cat_id]:
                                prod_dict["category_infos"] = category_cache[cat_id]
                                
                        # Fetch Unit
                        unit_id = prod_dict.get("unit_id")
                        if unit_id:
                            if unit_id not in unit_cache:
                                unit_cache[unit_id] = await get_shop_unit(shop_id=shop_id, unit_id=unit_id)
                            if unit_cache[unit_id]:
                                prod_dict["unit_infos"] = unit_cache[unit_id]

                        read_model = map_to_inventory_read_model(prod_dict)
                        await InventoryReadDbRepo.replace_inventory(read_model)
            except Exception as e:
                ic(f"Error syncing bulk inventory to read DB: {e}")

        return True
    


    async def update_all(self, data: List[UpdateAllProdInvSchema]) -> bool:
        inv_repo_obj = InventoryRepo(session=self.session)
        prod_repo_obj = ProductRepo(session=self.session)
        
        validated_data: Dict[str, List[Dict[str, Any]]] = {}
        product_serial_numbers: Dict[str, set] = {}
        
        product_tocheck = []
        variant_tocheck = []
        batch_tocheck = []
        serialno_tocheck = []
        
        create_stock_mov_adj = False
        shop_id = None

        # STEP-1: DUP VALIDATION & INCOMING DATA PARSING
        for prod in data:
            product_id = prod.product_id
            create_stock_mov_adj = prod.create_stock_mov_adj
            shop_id = prod.shop_id
            
            # Initialize containers if not present
            if product_id not in validated_data:
                validated_data[product_id] = []
            if product_id not in product_serial_numbers:
                product_serial_numbers[product_id] = set()

            # Check for identical product + variant + batch in the payload
            inc_variant_id = prod.variant_id
            inc_batch_id = prod.batch_infos.id if prod.batch_infos else None
            
            for inside_data in validated_data[product_id]:
                v_variant_id = inside_data.get("variant_id")
                v_batch_infos = inside_data.get("batch_infos")
                v_batch_id = v_batch_infos.get("id") if v_batch_infos else None

                if v_variant_id == inc_variant_id and v_batch_id == inc_batch_id:
                    ic("A duplicate combination of product, variant, and batch found in payload.")
                    return False

            # Validate duplicate serial numbers inside the payload for this product
            if prod.serialno_infos:
                for sn_info in prod.serialno_infos:
                    if sn_info.name:
                        if sn_info.name in product_serial_numbers[product_id]:
                            ic(f"Duplicate serial number '{sn_info.name}' for the same product found.")
                            return False
                        product_serial_numbers[product_id].add(sn_info.name)
                        if sn_info.id:
                            serialno_tocheck.append(sn_info.id)

            # Append data and track uniquely required database entities
            validated_data[product_id].append(prod.model_dump())
            
            if product_id and product_id not in product_tocheck:
                product_tocheck.append(product_id)
            if prod.variant_id and prod.variant_id not in variant_tocheck:
                variant_tocheck.append(prod.variant_id)
            if prod.batch_infos and prod.batch_infos.id and (prod.batch_infos.id not in batch_tocheck):
                batch_tocheck.append(prod.batch_infos.id)

        ic(product_tocheck, variant_tocheck, batch_tocheck, serialno_tocheck)

        # STEP-2: DATABASE VERIFICATION
        prod_checked_results = await prod_repo_obj.get_bulk_products_by_id(
            data=GetBulkProductsById(id=product_tocheck, shop_id=shop_id, include_serialno=True)
        )
        ic(prod_checked_results)
        ic(product_tocheck)

        if len(product_tocheck) != len(prod_checked_results):
            ic("Mismatched product count from DB verification.")
            return False

        # State tracking arrays for database operations
        batch_toadd = []
        serialno_toadd = []
        serialno_todelete = []
        stock_toadd = []
        stock_toupdate = []
        stl_toadd = []
        stl_toupdate = []
        rop_toadd = []
        rop_toupdate = []
        pricing_toadd = []
        pricing_toupdate = []
        
        validate_seriano_name = []
        stock_mov_adj_data = []
        product_toupdate: List[UpdateProductDbSchema] = []

        # STEP-3: PROCESSING DB ENTITIES AGAINST INCOMING PAYLOADS
        for prod_db in prod_checked_results:
            has_variant = prod_db['type_infos']['has_variant']
            has_batch = prod_db['type_infos']['has_batch']
            has_serialno = prod_db['type_infos']['has_serialno']
            existing_product_id = prod_db['id']
            existing_variants = prod_db.get('variants', {}) or {}

            validated_items = validated_data.get(existing_product_id)
            if not validated_items:
                ic("No configuration found for existing product ID.")
                return False

            # Loop through each payload targeting this specific product
            for inc_item in validated_items:
                inc_shop_id = inc_item['shop_id']
                inc_serialnos = inc_item.get('serialno_infos') or []
                inc_batch_infos = inc_item.get('batch_infos') or {}
                inc_batch_id = inc_batch_infos.get("id") if inc_batch_infos else None
                inc_variant_id = inc_item.get('variant_id')
                inc_stocks = inc_item.get('stocks') or 0
                inc_update_type = inc_item['type']
                inc_sell_price = inc_item.get('sell_price') or 0
                inc_buy_price = inc_item.get('buy_price') or 0
                inc_stl = inc_item.get('storage_location')
                inc_rop = inc_item.get('reorder_point')
                inc_entity_name = inc_item.get('entity_name')
                inc_gst = inc_item.get('gst')

                if has_variant and not inc_variant_id:
                    ic("Product requires a variant target but none was provided.")
                    return False

                # Extract fallback reference datasets based on product structure
                existing_stock_infos = {}
                existing_pricing_infos = {}
                existing_stl_info = {}
                existing_rop_info = {}
                existing_batch_list = []

                if has_variant:
                    variant_db_info = existing_variants.get(inc_variant_id)
                    if not variant_db_info:
                        ic("Target variant mismatch for the product.")
                        return False
                    
                    existing_stock_infos = variant_db_info.get('stock_infos') or {}
                    existing_pricing_infos = variant_db_info.get('pricing_infos') or {}
                    existing_stl_info = variant_db_info.get('storage_location_infos') or {}
                    existing_rop_info = variant_db_info.get('reorder_point_infos') or {}
                    existing_batch_list = variant_db_info.get('batch_infos') or []
                else:
                    existing_stock_infos = prod_db.get('stock_infos') or {}
                    existing_pricing_infos = prod_db.get('pricing_infos') or {}
                    existing_stl_info = prod_db.get('storage_location_infos') or {}
                    existing_rop_info = prod_db.get('reorder_point_infos') or {}
                    existing_batch_list = prod_db.get('batch_infos') or []

                # Process Batches if required
                is_batch_exists = False
                batch_names = [b['name'] for b in existing_batch_list if 'name' in b]

                if has_batch:
                    if not inc_batch_infos:
                        ic("Product configuration requires batch info details.")
                        return False
                    
                    if not inc_batch_infos.get('id') and (
                        not inc_batch_infos.get('name') or 
                        not inc_batch_infos.get('expiry_date') or 
                        not inc_batch_infos.get('manufacturing_date')
                    ):
                        ic("Batch information schema criteria failed.")
                        return False

                    if inc_batch_infos.get('name') in batch_names and not inc_batch_infos.get('id'):
                        ic("Duplicate batch name detected for this product stack.")
                        return False

                    # Scan structural batch details if an ID is present
                    if inc_batch_infos.get('id'):
                        for exc_batch in existing_batch_list:
                            if inc_batch_infos['id'] == exc_batch['id']:
                                is_batch_exists = True
                                inc_batch_id = exc_batch['id']
                                existing_stock_infos = exc_batch.get('stock_infos') or {}
                                existing_pricing_infos = exc_batch.get('pricing_infos') or {}
                                existing_stl_info = exc_batch.get('storage_location_infos') or {}
                                existing_rop_info = exc_batch.get('reorder_point_infos') or {}
                                break
                        if not is_batch_exists:
                            ic("Target batch ID not found in database records.")
                            return False
                    else:
                        # Clean assignment tracking for dynamically declared new batches
                        existing_stock_infos = {}
                        existing_pricing_infos = {}
                        existing_stl_info = {}
                        existing_rop_info = {}

                    if not is_batch_exists:
                        inc_batch_id = generate_uuid()
                        batch_toadd.append(
                            ProductBatches(
                                id=inc_batch_id,
                                shop_id=shop_id,
                                product_id=existing_product_id,
                                variant_id=inc_variant_id,
                                name=inc_batch_infos['name'],
                                expiration_infos={
                                    "expiry_date": str(inc_batch_infos['expiry_date']),
                                    "manufacturing_date": str(inc_batch_infos['manufacturing_date'])
                                }
                            )
                        )

                # Process Serial Numbers validations
                serialno_names = []
                if has_serialno:
                    if not inc_serialnos:
                        ic("Serial number configurations absent.")
                        return False
                    if len(inc_serialnos) != inc_stocks:
                        ic("Mismatch between physical inventory counts and serial units allocated.")
                        return False
                    
                    for serialno in inc_serialnos:
                        serialno_names.append(serialno['name'])

                # Determine Upsert Matrices (Add vs Update)
                is_stock_exists = bool(existing_stock_infos)
                is_pricing_exists = bool(existing_pricing_infos)
                is_stl_exists = bool(existing_stl_info)
                is_rop_exists = bool(existing_rop_info)

                # Stock Append Management
                if inc_stocks:
                    if is_stock_exists:
                        stock_toupdate.append(
                            UpdateInventoryStockDbSchema(
                                shop_id=inc_shop_id,
                                product_id=existing_product_id,
                                variant_id=inc_variant_id,
                                batch_id=inc_batch_id,
                                type=inc_update_type,
                                physical_stocks=inc_stocks,
                                reserved_stocks=0
                            )
                        )
                    else:
                        stock_toadd.append(
                            InventoryStocks(
                                id=generate_uuid(),
                                shop_id=inc_shop_id,
                                physical_stocks=inc_stocks,
                                reserved_stocks=0,
                                available_stocks=inc_stocks,
                                product_id=existing_product_id,
                                variant_id=inc_variant_id,
                                batch_id=inc_batch_id
                            )
                        )

                # Financial Pricing Setup
                if inc_buy_price and inc_sell_price:
                    if is_pricing_exists:
                        pricing_toupdate.append(
                            UpdateInventoryPricingDbSchema(
                                shop_id=inc_shop_id,
                                product_id=existing_product_id,
                                variant_id=inc_variant_id,
                                batch_id=inc_batch_id,
                                buy_price=inc_buy_price,
                                sell_price=inc_sell_price
                            )
                        )
                    else:
                        pricing_toadd.append(
                            InventoryPricings(
                                id=generate_uuid(),
                                shop_id=inc_shop_id,
                                product_id=existing_product_id,
                                variant_id=inc_variant_id,
                                batch_id=inc_batch_id,
                                buy_price=inc_buy_price,
                                sell_price=inc_sell_price
                            )
                        )

                # Storage Area Configurations
                if inc_stl:
                    if is_stl_exists:
                        stl_toupdate.append(
                            UpdateInventoryStorageLocationDbSchema(
                                shop_id=inc_shop_id,
                                product_id=existing_product_id,
                                variant_id=inc_variant_id,
                                batch_id=inc_batch_id,
                                name=inc_stl
                            )
                        )
                    else:
                        stl_toadd.append(
                            InventoryStoragelocations(
                                id=generate_uuid(),
                                shop_id=inc_shop_id,
                                product_id=existing_product_id,
                                variant_id=inc_variant_id,
                                batch_id=inc_batch_id,
                                name=inc_stl
                            )
                        )

                # Reorder Metric Point Triggers
                if inc_rop:
                    if is_rop_exists:
                        rop_toupdate.append(
                            UpdateInventoryReorderPointDbSchema(
                                shop_id=inc_shop_id,
                                product_id=existing_product_id,
                                variant_id=inc_variant_id,
                                batch_id=inc_batch_id,
                                reorder_point=inc_rop
                            )
                        )
                    else:
                        rop_toadd.append(
                            InventoryReorderPoint(
                                id=generate_uuid(),
                                shop_id=inc_shop_id,
                                product_id=existing_product_id,
                                variant_id=inc_variant_id,
                                batch_id=inc_batch_id,
                                reorder_point=inc_rop
                            )
                        )

                # Serial Handling Lifecycle
                if has_serialno and inc_serialnos:
                    if inc_update_type == "INCREMENT":
                        for serialno in inc_serialnos:
                            serialno_toadd.append(
                                ProductSerialNumbers(
                                    id=generate_uuid(),
                                    shop_id=inc_shop_id,
                                    product_id=existing_product_id,
                                    variant_id=inc_variant_id,
                                    batch_id=inc_batch_id,
                                    name=serialno['name'],
                                    status="AVAILABLE"
                                )
                            )
                    elif inc_update_type == "DECREMENT":
                        for serialno in inc_serialnos:
                            if not serialno.get("id"):
                                ic("Required serial identifier parameters missing for dynamic removals.")
                                return False
                            serialno_todelete.append(serialno['id'])

                if has_serialno:
                    validate_seriano_name.append({
                        'shop_id': inc_shop_id,
                        'product_id': existing_product_id,
                        'variant_id': inc_variant_id,
                        'batch_id': inc_batch_id,
                        'names': serialno_names
                    })

                stock_mov_adj_data.append({
                    'product_id': existing_product_id,
                    'variant_id': inc_variant_id,
                    'batch_id': inc_batch_id,
                    'serial_numbers': inc_serialnos,
                    'type': inc_update_type,
                    'stocks': inc_stocks,
                    'shop_id': inc_shop_id,
                    'entity_name': inc_entity_name
                })

                product_toupdate.append(
                    UpdateProductDbSchema(
                        id=existing_product_id,
                        shop_id=inc_shop_id,
                        gst=inc_gst,
                        is_active=True
                    )
                )

        # STEP-4: DATABASE EXECUTION
        if batch_toadd and has_batch:
            await prod_repo_obj.create_bulk_batch(data=batch_toadd)
        
        if serialno_toadd and has_serialno:
            res_serialno_names = await prod_repo_obj.verify_bulk_serialno_name(data=validate_seriano_name)
            if res_serialno_names:
                ic("Unique serial criteria breached. System match collision detected.")
                return False
            await prod_repo_obj.create_bulk_selialno(data=serialno_toadd)

        if serialno_todelete and has_serialno:
            await prod_repo_obj.delete_bulk_serialno(data=serialno_todelete)

        if stock_toadd:
            await inv_repo_obj.create_bulk_stocks(data=stock_toadd)

        if stock_toupdate:
            res_stocks = await inv_repo_obj.update_bulk_stocks(data=stock_toupdate)
            
            # Safe mapping for zero-stock status changes without list mutation bugs
            zero_stock_product_ids = {stock['product_id'] for stock in res_stocks if stock.get('available_stocks') == 0}
            
            final_product_updates = []
            for p_update in product_toupdate:
                if p_update.id in zero_stock_product_ids:
                    final_product_updates.append(
                        UpdateProductDbSchema(
                            id=p_update.id,
                            shop_id=p_update.shop_id,
                            gst=p_update.gst,
                            is_active=False
                        )
                    )
                else:
                    final_product_updates.append(p_update)
            product_toupdate = final_product_updates

        if stl_toadd:
            await inv_repo_obj.create_bulk_storage_location(data=stl_toadd)
        if stl_toupdate:
            await inv_repo_obj.update_bulk_storage_location(data=stl_toupdate)
            
        if rop_toadd:
            await inv_repo_obj.create_bulk_reorder_point(data=rop_toadd)
        if rop_toupdate:
            await inv_repo_obj.update_bulk_reorder_point(data=rop_toupdate)

        if pricing_toadd:
            await inv_repo_obj.create_bulk_pricing(data=pricing_toadd)
        if pricing_toupdate:
            await inv_repo_obj.update_bulk_pricing(data=pricing_toupdate)

        if product_toupdate:
            await prod_repo_obj.update_bulk_product(data=product_toupdate)

        # FINAL COMPILATION & VIEW WRITE SYNCS
        await ProdInvReadDbRepo.add_updatereaddb(
            shop_id=shop_id,
            product_ids=product_tocheck,
            session=self.session
        )

        if create_stock_mov_adj:
            await emit_stock_mov_adj(session=self.session, data=stock_mov_adj_data)


        return True

            


