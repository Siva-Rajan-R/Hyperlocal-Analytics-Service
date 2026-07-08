from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from schemas.v1.request_schemas.customfield_schema import (
    CreateCustomFieldSchema, UpdateCustomFieldSchema,
    CreateCustomFieldValueSchema, UpdateCustomFieldValueSchema,
    BulkCreateCustomFieldValuesSchema
)
from schemas.v1.db_schemas.customfield_schema import CreateCustomFieldDbSchema, CreateCustomFieldValueDbSchema
from ..repos.customfield_repo import CustomFieldsRepo

class CustomFieldsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CustomFieldsRepo(session)

    async def create_field(self,data: CreateCustomFieldSchema) -> dict:
        # Verify field name doesn't already exist for this shop
        existing = await self.repo.get_field_by_name(field_name=data.field_name, shop_id=data.shop_id)
        if existing:
            raise HTTPException(status_code=400, detail="Custom field with this name already exists")

        field_id = generate_uuid()
        db_data = CreateCustomFieldDbSchema(
            id=field_id,
            **data.model_dump()
        )
        
        await self.repo.create_field(db_data)
        return {"success": True, "id": field_id}

    async def update_field(self,data: UpdateCustomFieldSchema) -> dict:
        existing = await self.repo.get_field_by_id(field_id=data.field_id, shop_id=data.shop_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Custom field not found")

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return {"success": True, "message": "No fields to update"}
            
        updated_id = await self.repo.update_field(field_id=data.field_id, shop_id=data.shop_id, update_data=data.update_data)
        if not updated_id:
            raise HTTPException(status_code=500, detail="Failed to update custom field")
            
        return {"success": True, "id": updated_id}

    async def delete_field(self, field_id: str, shop_id: str) -> dict:
        existing = await self.repo.get_field_by_id(field_id=field_id, shop_id=shop_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Custom field not found")
            
        success = await self.repo.delete_field(field_id=field_id, shop_id=shop_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete custom field")
            
        return {"success": True}

    async def get_all_fields(self, shop_id: str) -> list:
        return await self.repo.get_all_fields(shop_id=shop_id)

    async def get_field(self, field_id: str, shop_id: str) -> dict:
        field = await self.repo.get_field_by_id(field_id=field_id, shop_id=shop_id)
        if not field:
            raise HTTPException(status_code=404, detail="Custom field not found")
        return field

    # --- Values ---

    async def upsert_value(self,data: CreateCustomFieldValueSchema) -> dict:
        # Verify field exists
        field = await self.repo.get_field_by_id(field_id=data.field_id, shop_id=data.shop_id)
        if not field:
            raise HTTPException(status_code=404, detail=f"Custom field {data.field_id} not found")
            
        value_id = generate_uuid()
        db_data = CreateCustomFieldValueDbSchema(
            id=value_id,
            shop_id=data.shop_id,
            **data.model_dump()
        )
        
        await self.repo.upsert_field_value(db_data)
        return {"success": True}

    async def bulk_upsert_values(self, data: BulkCreateCustomFieldValuesSchema) -> dict:
        for val in data.values:
            field_name = val.get("field_name")
            value = val.get("value")
            if not field_name or not value:
                continue
                
            field = await self.repo.get_field_by_name(field_name=field_name, shop_id=data.shop_id)
            if not field:
                raise HTTPException(status_code=404, detail=f"Custom field {field_name} not found")
                
            db_data = CreateCustomFieldValueDbSchema(
                id=generate_uuid(),
                shop_id=data.shop_id,
                product_id=data.product_id,
                field_id=field['id'],
                value=value
            )
            await self.repo.upsert_field_value(db_data)
            
        return {"success": True}

    async def get_values_by_product(self, product_id: str, shop_id: str) -> list:
        return await self.repo.get_values_by_product_id(product_id=product_id, shop_id=shop_id)
