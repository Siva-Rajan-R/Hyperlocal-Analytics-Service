from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from icecream import ic
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction
from ..models.customfield_model import ProductCustomFields, ProductCustomFieldsValues
from schemas.v1.db_schemas.customfield_schema import CreateCustomFieldDbSchema, CreateCustomFieldValueDbSchema

class CustomFieldsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Custom Fields (Definitions) ---
    
    @start_db_transaction
    async def create_field(self, data: CreateCustomFieldDbSchema) -> bool:
        self.session.add(ProductCustomFields(**data.model_dump(mode='json')))
        return True

    @start_db_transaction
    async def update_field(self, field_id: str, shop_id: str, update_data: dict) -> Optional[str]:
        stmt = (
            update(ProductCustomFields)
            .where(ProductCustomFields.id == field_id, ProductCustomFields.shop_id == shop_id)
            .values(**update_data)
            .returning(ProductCustomFields.id)
        )
        res = (await self.session.execute(stmt)).scalar_one_or_none()
        return res

    @start_db_transaction
    async def delete_field(self, field_id: str, shop_id: str) -> bool:
        # Note: Depending on constraints, deleting a field might cascade delete its values
        stmt = delete(ProductCustomFields).where(
            ProductCustomFields.id == field_id,
            ProductCustomFields.shop_id == shop_id
        )
        res = await self.session.execute(stmt)
        return res.rowcount > 0

    async def get_field_by_id(self, field_id: str, shop_id: str) -> Optional[dict]:
        stmt = select(ProductCustomFields).where(
            ProductCustomFields.id == field_id, 
            ProductCustomFields.shop_id == shop_id
        )
        res = (await self.session.execute(stmt)).scalars().first()
        if res:
            return {c.name: getattr(res, c.name) for c in res.__table__.columns}
        return None
        
    async def get_field_by_name(self, field_name: str, shop_id: str) -> Optional[dict]:
        stmt = select(ProductCustomFields).where(
            ProductCustomFields.field_name == field_name, 
            ProductCustomFields.shop_id == shop_id
        )
        res = (await self.session.execute(stmt)).scalars().first()
        if res:
            return {c.name: getattr(res, c.name) for c in res.__table__.columns}
        return None

    async def get_all_fields(self, shop_id: str) -> List[dict]:
        stmt = select(ProductCustomFields).where(ProductCustomFields.shop_id == shop_id)
        res = (await self.session.execute(stmt)).scalars().all()
        return [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in res]

    # --- Custom Fields Values (Assignments) ---
    
    @start_db_transaction
    async def upsert_field_value(self, data: CreateCustomFieldValueDbSchema) -> bool:
        # Check if exists
        stmt = select(ProductCustomFieldsValues).where(
            ProductCustomFieldsValues.product_id == data.product_id,
            ProductCustomFieldsValues.field_id == data.field_id,
            ProductCustomFieldsValues.shop_id == data.shop_id
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        
        if existing:
            update_stmt = (
                update(ProductCustomFieldsValues)
                .where(ProductCustomFieldsValues.id == existing.id)
                .values(value=data.value)
            )
            await self.session.execute(update_stmt)
        else:
            self.session.add(ProductCustomFieldsValues(**data.model_dump(mode='json')))
            
        return True
        
    async def get_values_by_product_id(self, product_id: str, shop_id: str) -> List[dict]:
        stmt = select(ProductCustomFieldsValues).where(
            ProductCustomFieldsValues.product_id == product_id,
            ProductCustomFieldsValues.shop_id == shop_id
        )
        res = (await self.session.execute(stmt)).scalars().all()
        return [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in res]
