from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.exceptions import HTTPException
from schemas.v1.prod_inv_schemas.request_schemas import CreateProdInvSchema,UpdateProdInvSchema,DeleteProdInvSchema
from hyperlocal_platform.core.models.req_res_models import SuccessResponseTypDict,BaseResponseTypDict,ErrorResponseTypDict
from messaging.saga_producer import SagaProducer,CreateSagaStateSchema,SagaStatusEnum
from hyperlocal_platform.core.enums.saga_state_enum import SagaStepsValueEnum
from hyperlocal_platform.core.typed_dicts.saga_status_typ_dict import SagaStateExecutionTypDict
from hyperlocal_platform.core.enums.routingkey_enum import RoutingkeyActions,RoutingkeyState,RoutingkeyVersions
from hyperlocal_platform.core.utils.routingkey_builder import generate_routingkey
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from core.constants import SERVICE_NAME
from infras.primary_db.services.prod_inv_service import ProductInventoryService
from schemas.v1.product_schemas.request_schemas import GetAllProductSchema,GetProductsById,GetProductsByShopId
from infras.primary_db.repos.product_repo import ProductRepo
from core.data_formats.enums.inventory_enums import InventoryFetchMode
from core.utils.calculate_offer import calculate_offer
from core.utils.validate_offer import validate_offer_input
from icecream import ic
from infras.read_db.repos.prod_inv_repo import ProdInvReadDbRepo
from infras.primary_db.services.customfield_service import CustomFieldsService
from schemas.v1.prod_inv_schemas.request_schemas import CreateProdInvSchema,UpdateProdInvSchema,DeleteProdInvSchema
from schemas.v1.inventory_schemas.request_schemas import ReserveInventorySchema,ReleaseInventorySchema,CommitInventorySchema,ReleaseItemInventorySchema
from core.utils.validate_custom_fields import validate_and_filter_custom_fields
from schemas.v1.request_schemas.customfield_schema import BulkCreateCustomFieldValuesSchema
# [InventoryGetResponseSchema(**r) for r in res] if res else []

class HandleProdInvRequest:
    def __init__(self,session:AsyncSession):
        self.session=session
    
    async def create(self,data:CreateProdInvSchema):
        """
        Instead of creation, we need to trigger the event that event will handle the adding
        """ 
        if data.type_infos.has_variant and not data.variant_infos:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error => Creating Inventory",
                    description="Please provide atleast one variant when it was enabled",
                    success=False,
                    status_code=400
                ),
                
            )
        
        cust_field_obj=CustomFieldsService(session=self.session)
        fields=await cust_field_obj.get_all_fields(shop_id=data.shop_id)
        
        valid_custom_fields = validate_and_filter_custom_fields(data.custom_fields, fields)
        
        defined_fields_map = {f['field_name']: f['id'] for f in fields}
        cf_values = []
        for key, val in valid_custom_fields.items():
            if key in defined_fields_map:
                cf_values.append({"field_id": defined_fields_map[key], "value": str(val), "field_name": key})
                
        data.custom_fields = {"values": cf_values} if cf_values else {}
        
        res=await ProductInventoryService(session=self.session).create(data=data)
        ic(res)
        
        if res:
            await self.session.commit()
            return SuccessResponseTypDict(
                detail=BaseResponseTypDict(
                    status_code=201,
                    success=True,
                    msg="Inventory Created Successfully"
                ),
                data=res
            )
        
        return HTTPException(
             status_code=400,
             detail=ErrorResponseTypDict(
                  msg="Error => Creating Inventory",
                  description="Invalid payload for creating invetory product or already exists",
                  success=False,
                  status_code=400
             ),
             
        )
    
    async def update(self,data:UpdateProdInvSchema):
        if data.type_infos.has_variant and not data.variant_infos:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error => Creating Inventory",
                    description="Please provide atleast one variant when it was enabled",
                    success=False,
                    status_code=400
                ),
            )
        cust_field_obj=CustomFieldsService(session=self.session)
        fields=await cust_field_obj.get_all_fields(shop_id=data.shop_id)
        
        valid_custom_fields = validate_and_filter_custom_fields(data.custom_fields, fields)
        
        defined_fields_map = {f['field_name']: f['id'] for f in fields}
        cf_values = []
        for key, val in valid_custom_fields.items():
            if key in defined_fields_map:
                cf_values.append({"field_id": defined_fields_map[key], "value": str(val), "field_name": key})
                
        data.custom_fields = {"values": cf_values} if cf_values else {}
        
        res=await ProductInventoryService(session=self.session).update(data=data)
        ic(res)
        if res:

             return SuccessResponseTypDict(
                  detail=BaseResponseTypDict(
                       status_code=200,
                       success=True,
                       msg="Inventory Updated Successfully"
                  )
             )
        
        return HTTPException(
             status_code=400,
             detail=ErrorResponseTypDict(
                  msg="Error => Updating Inventory",
                  description="Invalid payload for updating invetory product",
                  success=False,
                  status_code=400
             ),
             
        )
    
    async def delete(self,data:DeleteProdInvSchema):
        res=await ProductInventoryService(session=self.session).delete(data=data)
        ic(res)
        if res:
             return SuccessResponseTypDict(
                  detail=BaseResponseTypDict(
                       status_code=200,
                       success=False,
                       msg="Inventory Deleted Successfully"
                  )
             )
        
        return HTTPException(
             status_code=400,
             detail=ErrorResponseTypDict(
                  msg="Error => Deleting Inventory",
                  description="Invalid payload for deleting invetory product",
                  success=False,
                  status_code=400
             ),
             
        )
    
    async def get(self,data:GetAllProductSchema):
        # res=await ProductRepo(session=self.session).get_products(data=data)
        res=await ProdInvReadDbRepo.get_all(data=data)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                msg="Inventories fetched successfully",
                status_code=200,
                success=True
            ),
            data=res
        )
    async def getby_shop_id(self,data:GetProductsByShopId):
        # res=await ProductRepo(session=self.session).get_products_by_shop_id(data=data)
        res=await ProdInvReadDbRepo.get_by_shop_id(data=data)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                msg="Inventories fetched successfully",
                status_code=200,
                success=True
            ),
            data=res
        )
    
    async def getby_id(self,data:GetProductsById):
        # res=await ProductRepo(session=self.session).get_products_by_id(data=data)
        res=await ProdInvReadDbRepo.get_by_id(data=data)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                msg="Inventories fetched successfully",
                status_code=200,
                success=True
            ),
            data=res
        )
        
    async def search(self, shop_id: str, query: str, limit: int = 5):
        from infras.read_db.repos.supplier_repo import InventoryReadDbRepo
        from schemas.v1.request_schemas.inventory_schema import GetInventoryByShopIdSchema
        req_data = GetInventoryByShopIdSchema(shop_id=shop_id, query=query, limit=limit, offset=1)
        res = await InventoryReadDbRepo.get_all_inventories(data=req_data)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                msg="Inventory fetched successfully",
                status_code=200,
                success=True
            ),
            data=res
        )