from models.repo_models.base_repo_model import BaseRepoModel
from models.service_models.base_service_model import BaseServiceModel
# from ..models.product_model import Products,ProductBatches,ProductSerialNumbers,ProductVariants
from ..models.inventory_model import InventoryPricings,InventoryStocks,InventoryStoragelocations,InventoryReorderPoint,InventoryReservation
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select,update,delete,func,or_,and_,String,case,cast,Text,literal,literal_column,text,bindparam,null
from sqlalchemy.dialects.postgresql import JSONB,ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
# from schemas.v1.product_schemas.db_schemas import CreateProductBatchDbSchema,CreateProductDbSchema,CreateProductSerialnoDbSchema,CreateProductVariantDbSchema,UpdateProductBatchDbSchema,UpdateProductDbSchema,UpdateProductSerialnoDbSchema,UpdateProductVariantDbSchema,DeleteProductDbSchema
# from schemas.v1.product_schemas.request_schemas import GetAllProductSchema,GetProductsById,GetProductsByShopId
from schemas.v1.inventory_schemas.db_schemas import CreateInventoryPricingDbSchema,CreateInventoryStockDbSchema,CreateInventoryStorageLocationDbSchema,UpdateInventoryPricingDbSchema,UpdateInventoryStockDbSchema,UpdateInventoryStorageLocationDbSchema,CreateInventoryReorderPointDbSchema,UpdateInventoryReorderPointDbSchema
from schemas.v1.inventory_schemas.request_schemas import VerifyInventoryCombinedSchema, CommitInventorySchema
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction
from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from typing import Optional,List
from icecream import ic
from core.data_formats.enums.stock_adj_enums import StockAdjustmentTypesEnum
from messaging.main import RabbitMQMessagingConfig
from schemas.v1.prod_inv_schemas.request_schemas import CreateProdInvSchema,UpdateProdInvSchema,DeleteProdInvSchema
from schemas.v1.inventory_schemas.request_schemas import ReserveInventorySchema,ReleaseInventorySchema,CommitInventorySchema,ReleaseItemInventorySchema
import datetime
from .product_repo import ProductRepo,UpdateProductSerialnoDbSchema
from core.data_formats.enums.product_enums import ProductSerialnoStatusEnums
from helpers.emit_stock_mov_adj import emit_stock_mov_adj
from infras.read_db.repos.prod_inv_repo import ProdInvReadDbRepo



class InventoryRepo:
    def __init__(self,session:AsyncSession):
        self.session=session
        self.invetory_pricing_cols=(
            InventoryPricings.id,InventoryPricings.buy_price,InventoryPricings.sell_price,InventoryPricings.additional_infos,
            InventoryPricings.created_at,InventoryPricings.updated_at
        )
        self.inventory_stl_cols=(
            InventoryStoragelocations.id,InventoryStoragelocations.name,InventoryStoragelocations.additional_infos,
            InventoryStoragelocations.created_at,InventoryStoragelocations.updated_at
        )
        self.inventory_stocks_cols=(
            InventoryStocks.id,InventoryStocks.physical_stocks,InventoryStocks.reserved_stocks,InventoryStocks.available_stocks,
            InventoryStocks.created_at,InventoryStocks.updated_at,InventoryStocks.additional_infos
        )
        self.inventory_rop_cols=(
            InventoryReorderPoint.id,InventoryReorderPoint.reorder_point,InventoryReorderPoint.additional_infos
        )

    @start_db_transaction
    async def create_bulk_stocks(self,data:List[InventoryStocks]):
        if data:
            self.session.add_all(data)
        return True
    
    @start_db_transaction
    async def create_bulk_pricing(self,data: List[InventoryPricings]):
        ic(data)
        if data:
            ic("bulk pricing")
            self.session.add_all(data)

        return True


    @start_db_transaction
    async def create_bulk_storage_location(self,data: List[InventoryStoragelocations]):
        if data:
            ic("bulk stl")
            self.session.add_all(data)
        return True


    @start_db_transaction
    async def create_bulk_reorder_point(self,data: List[InventoryReorderPoint]):
        if data:
            ic("bulk ro")
            self.session.add_all(data)
        return True
    


    @start_db_transaction
    async def update_bulk_stocks(self, data: List[UpdateInventoryStockDbSchema]):
        if not data:
            return True

        updated_keys = []

        for d in data:
            amount = d.physical_stocks or 0.0

            stmt = (
                update(InventoryStocks)
                .where(
                    InventoryStocks.product_id == d.product_id,
                    InventoryStocks.variant_id.is_not_distinct_from(d.variant_id),
                    InventoryStocks.batch_id.is_not_distinct_from(d.batch_id),
                )
            )

            if d.type == "INCREMENT":
                stmt = stmt.values(
                    physical_stocks=InventoryStocks.physical_stocks + amount,
                    available_stocks=InventoryStocks.available_stocks + amount,
                )

            elif d.type == "DECREMENT":
                stmt = (
                    stmt.where(
                        InventoryStocks.available_stocks >= amount
                    )
                    .values(
                        physical_stocks=InventoryStocks.physical_stocks - amount,
                        available_stocks=InventoryStocks.available_stocks - amount,
                    )
                )

            else:  # DIRECT
                stmt = stmt.values(
                    physical_stocks=d.physical_stocks,
                    reserved_stocks=d.reserved_stocks,
                    available_stocks=(d.physical_stocks or 0.0) - (d.reserved_stocks or 0.0),
                )

            result = await self.session.execute(stmt)

            if d.type == "DECREMENT" and result.rowcount == 0:
                raise ValueError(
                    f"Insufficient available stock for Product '{d.product_id}'"
                )

            updated_keys.append(
                {
                    "product_id": d.product_id,
                    "variant_id": d.variant_id,
                    "batch_id": d.batch_id,
                }
            )

        # Fetch updated rows
        conditions = [
            and_(
                InventoryStocks.product_id == k["product_id"],
                InventoryStocks.variant_id.is_not_distinct_from(k["variant_id"]),
                InventoryStocks.batch_id.is_not_distinct_from(k["batch_id"]),
            )
            for k in updated_keys
        ]

        updated_stocks = (
            (
                await self.session.execute(
                    select(InventoryStocks).where(or_(*conditions))
                )
            )
        )
        # mapping_res=updated_stocks.mappings().all()
        scalar_res=updated_stocks.scalars().all()

        from ...read_db.services.inventory_service import ReadDbInventoryService

        sync_data = [
            {
                "product_id": stock.product_id,
                "variant_id": stock.variant_id,
                "batch_id": stock.batch_id,
                "physical_stocks": stock.physical_stocks,
                "reserved_stocks": stock.reserved_stocks or 0,
                "available_stocks":stock.available_stocks
            }
            for stock in scalar_res
        ]

        if sync_data:
            await ReadDbInventoryService().update_stocks_bulk(sync_data)

        ic(scalar_res,sync_data)
        return sync_data
    
    @start_db_transaction
    async def update_bulk_pricing(self,data:List[UpdateInventoryPricingDbSchema]):
        if not data:
            return True
        
        stmt = (
            update(InventoryPricings)
            .where(
                InventoryPricings.shop_id == bindparam("b_shop_id"),
                InventoryPricings.product_id == bindparam("b_product_id"),
                InventoryPricings.variant_id.is_not_distinct_from(bindparam("b_variant_id")),
                InventoryPricings.batch_id.is_not_distinct_from(bindparam("b_batch_id")),
            )
            .values(
                buy_price=bindparam("buy_price"),
                sell_price=bindparam("sell_price")
            )
            .execution_options(synchronize_session=False)
        )
        conn = await self.session.connection()
        res=(
            await conn.execute(
                stmt,
                [
                    {
                        "b_shop_id":d.shop_id,
                        "b_product_id":d.product_id,
                        "b_variant_id":d.variant_id,
                        "b_batch_id":d.batch_id,
                        "buy_price":d.buy_price,
                        "sell_price":d.sell_price,
                    }
                    for d in data
                ]
            )
        )

        ic(res)
        return True


    @start_db_transaction
    async def update_bulk_storage_location(self,data:List[UpdateInventoryStorageLocationDbSchema]):
        if not data:
            return True
        
        stmt = (
            update(InventoryStoragelocations)
            .where(
                InventoryStoragelocations.shop_id == bindparam("b_shop_id"),
                InventoryStoragelocations.product_id == bindparam("b_product_id"),
                InventoryStoragelocations.variant_id.is_not_distinct_from(bindparam("b_variant_id")),
                InventoryStoragelocations.batch_id.is_not_distinct_from(bindparam("b_batch_id")),
            )
            .values(
                name=bindparam("name"),
                
            )
            .execution_options(synchronize_session=False)
        )
        conn = await self.session.connection()
        res=(
            await conn.execute(
                stmt,
                [
                    {
                        "b_shop_id":d.shop_id,
                        "b_product_id":d.product_id,
                        "b_variant_id":d.variant_id,
                        "b_batch_id":d.batch_id,
                        "name":d.name,
                    }
                    for d in data
                ]
            )
        )

        ic(res)
        return True
    

    @start_db_transaction
    async def update_bulk_reorder_point(self,data:List[UpdateInventoryReorderPointDbSchema]):
        if not data:
            return True

        stmt = (
            update(InventoryReorderPoint)
            .where(
                InventoryReorderPoint.shop_id == bindparam("b_shop_id"),
                InventoryReorderPoint.product_id == bindparam("b_product_id"),
                InventoryReorderPoint.variant_id.is_not_distinct_from(bindparam("b_variant_id")),
                InventoryReorderPoint.batch_id.is_not_distinct_from(bindparam("b_batch_id")),
            )
            .values(
                reorder_point=bindparam("reorder_point"),
            )
            .execution_options(synchronize_session=False)
        )
        conn = await self.session.connection()
        res=(
            await conn.execute(
                stmt,
                [
                    {
                        "b_shop_id":d.shop_id,
                        "b_product_id":d.product_id,
                        "b_variant_id":d.variant_id,
                        "b_batch_id":d.batch_id,
                        "reorder_point":d.reorder_point,
                    }
                    for d in data
                ]
            )
        )

        ic(res)
        return True
    

    async def get_bulk_stocks(self,data:List[dict]):
        if not data:
            return []
        
        stmt = select(
            InventoryStocks.id,
            InventoryStocks.product_id,
            InventoryStocks.variant_id,
            InventoryStocks.batch_id,
            InventoryStocks.available_stocks,
            InventoryStocks.physical_stocks,
            InventoryStocks.reserved_stocks
        ).where(
            InventoryStocks.shop_id == bindparam("b_shop_id"),
            InventoryStocks.product_id == bindparam("b_product_id"),
            InventoryStocks.variant_id.is_not_distinct_from(bindparam("b_variant_id")),
            InventoryStocks.batch_id.is_not_distinct_from(bindparam("b_batch_id")),
        ).execution_options(synchronize_session=False)

        conn = await self.session.connection()
        res=(
            await conn.execute(
                stmt,
                [
                    {
                        "b_shop_id":d.shop_id,
                        "b_product_id":d.product_id,
                        "b_variant_id":d.variant_id,
                        "b_batch_id":d.batch_id
                    }
                    for d in data
                ]
            )
        )

        ic(res)
        return True

    async def verify_bulk_stock(self, data: List[str]):
        stmt = select(InventoryStocks.id).where(InventoryStocks.id.in_(data))
        res = (await self.session.execute(stmt)).scalars().all()
        ic(res)
        return res

    async def verify_bulk_pricing(self, data: List[str]):
        stmt = select(InventoryPricings.id).where(InventoryPricings.id.in_(data))
        res = (await self.session.execute(stmt)).scalars().all()
        ic(res)
        return res

    async def verify_bulk_storage_location(self, data: List[str]):
        stmt = select(InventoryStoragelocations.id).where(InventoryStoragelocations.id.in_(data))
        res = (await self.session.execute(stmt)).scalars().all()
        ic(res)
        return res

    async def verify_bulk_reorder_point(self, data: List[str]):
        stmt = select(InventoryReorderPoint.id).where(InventoryReorderPoint.id.in_(data))
        res = (await self.session.execute(stmt)).scalars().all()
        ic(res)
        return res

    async def verify_inventory_combined(self, data: VerifyInventoryCombinedSchema):
        stocks = []
        pricings = []
        storage_locations = []
        reorder_points = []
        
        if data.stocks:
            res = await self.verify_bulk_stock(data=data.stocks)
            ic(res)
            stocks.extend(res)

        if data.pricings:
            res = await self.verify_bulk_pricing(data=data.pricings)
            ic(res)
            pricings.extend(res)

        if data.storage_locations:
            res = await self.verify_bulk_storage_location(data=data.storage_locations)
            ic(res)
            storage_locations.extend(res)

        if data.reorder_points:
            res = await self.verify_bulk_reorder_point(data=data.reorder_points)
            ic(res)
            reorder_points.extend(res)

        return {
            "stocks": stocks,
            "pricings": pricings,
            "storage_locations": storage_locations,
            "reorder_points": reorder_points
        }
        
    
    @start_db_transaction
    async def reserve_stock(self, data: ReserveInventorySchema):
        # data format: {"session_id", "product_id", "variant_id", "batch_id", "shop_id", "qty", "expires_at"}
        session_id = data.session_id
        product_id = data.product_id
        variant_id = data.variant_id
        batch_id = data.batch_id
        shop_id = data.shop_id
        new_qty = float(data.qty)
        expires_at = data.expires_at
        serialno_infos=[sn.model_dump() for sn in data.serialno_infos or []]

        # Find existing active reservation
        stmt_res = select(InventoryReservation).where(
            InventoryReservation.session_id == session_id,
            InventoryReservation.product_id == product_id,
            InventoryReservation.variant_id == variant_id,
            InventoryReservation.batch_id == batch_id,
            InventoryReservation.status == "ACTIVE"
        ).with_for_update()
        
        reservation = (await self.session.execute(stmt_res)).scalars().first()
        
        old_qty = 0
        prev_serialno_infos=reservation.serialno_infos if reservation else []
        new_serialno_infos=serialno_infos
        serialno_toverify=[]

        ic(new_serialno_infos,prev_serialno_infos)

        if prev_serialno_infos:
            reformed_serialno_infos={}
            for serialno in prev_serialno_infos:
                reformed_serialno_infos[serialno['id']]=serialno['name']
            
            for i,serialno in enumerate(new_serialno_infos):
                if serialno['id'] in reformed_serialno_infos:
                    new_serialno_infos.pop(i)
                else:
                    serialno_toverify.append(serialno['id'])
        

        ic(prev_serialno_infos,new_serialno_infos)
        is_serialno_exists=await ProductRepo(session=self.session).verify_bulk_serialno(data=serialno_toverify)
        if len(is_serialno_exists)!=len(serialno_toverify):
            ic("Serialno does not exists")
            return False


        if reservation:
            old_qty = reservation.qty
            reservation.qty = new_qty
            reservation.expires_at = expires_at
            reservation.serialno_infos=prev_serialno_infos+new_serialno_infos
        else:
            from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
            reservation = InventoryReservation(
                id=generate_uuid(),
                session_id=session_id,
                shop_id=shop_id,
                product_id=product_id,
                variant_id=variant_id,
                batch_id=batch_id,
                serialno_infos=new_serialno_infos,
                qty=new_qty,
                status="ACTIVE",
                expires_at=expires_at
            )
            self.session.add(reservation)

        delta = new_qty - old_qty
        if delta == 0:
            return True

        # Update InventoryStocks with lock
        stmt_stock = select(InventoryStocks).where(
            InventoryStocks.shop_id == shop_id,
            InventoryStocks.product_id == product_id,
            InventoryStocks.variant_id == variant_id,
            InventoryStocks.batch_id == batch_id
        ).with_for_update()
        
        stock_record = (await self.session.execute(stmt_stock)).scalars().first()
        
        
        if not stock_record:
            ic("Stock record not found for reservation")
            raise ValueError("Stock record not found")
            
        if delta > stock_record.available_stocks:
            raise ValueError(f"Insufficient stock for reservation. Available: {stock_record.available_stocks}, Requested: {delta}")

        ic(stock_record.available_stocks)
        stock_record.reserved_stocks = (stock_record.reserved_stocks or 0) + delta
        stock_record.available_stocks = stock_record.physical_stocks - stock_record.reserved_stocks

        if new_serialno_infos:
            await ProductRepo(session=self.session).update_bulk_serialno(
                data=[
                    UpdateProductSerialnoDbSchema(
                        id=d['id'],
                        shop_id=shop_id,
                        status=ProductSerialnoStatusEnums.RESERVED
                    )
                    for d in new_serialno_infos
                ]
            )

            prev_serialno_infos+=serialno_infos
            reservation.serialno_infos=prev_serialno_infos

        ic(stock_record.physical_stocks,stock_record.reserved_stocks)
        readdb_res=await ProdInvReadDbRepo.add_updatereaddb(session=self.session,shop_id=shop_id,product_ids=[product_id])
        await self.session.commit()
        ic(readdb_res)
        
        return True

    @start_db_transaction
    async def release_reservations(self, data:ReleaseInventorySchema):
        stmt_res = select(InventoryReservation).where(
            InventoryReservation.session_id == data.session_id,
            InventoryReservation.status == "ACTIVE"
        ).with_for_update()
        
        reservations = (await self.session.execute(stmt_res)).scalars().all()
        product_ids=[]
        shop_id=None
        for res in reservations:
            # Update InventoryStocks with lock
            stmt_stock = select(InventoryStocks).where(
                InventoryStocks.shop_id == res.shop_id,
                InventoryStocks.product_id == res.product_id,
                InventoryStocks.variant_id == res.variant_id,
                InventoryStocks.batch_id == res.batch_id
            ).with_for_update()


            serialno_infos=res.serialno_infos
            if serialno_infos:
                await ProductRepo(session=self.session).update_bulk_serialno(
                    data=[
                        UpdateProductSerialnoDbSchema(
                            id=d['id'],
                            shop_id=res.shop_id,
                            status=ProductSerialnoStatusEnums.AVAILABLE
                        )
                        for d in serialno_infos
                    ]
                )
            stock_record = (await self.session.execute(stmt_stock)).scalars().first()

            product_ids.append(res.product_id) 
            shop_id=res.shop_id  
            res.status = "RELEASED"
        
        readdb_res=await ProdInvReadDbRepo.add_updatereaddb(session=self.session,shop_id=shop_id,product_ids=product_ids)
        ic(readdb_res)
            
        return True

    @start_db_transaction
    async def release_reservation_item(self, data:ReleaseItemInventorySchema):
        stmt_res = select(InventoryReservation).where(
            InventoryReservation.session_id == data.session_id,
            InventoryReservation.product_id == data.product_id,
            InventoryReservation.status == "ACTIVE",
            InventoryReservation.variant_id == data.variant_id,
            InventoryReservation.batch_id == data.batch_id
        ).with_for_update()

        
        reservation = (await self.session.execute(stmt_res)).scalars().first()
        if not reservation:
            ic("No reservation found for this item")
            return False
        
        # Update InventoryStocks with lock
        stmt_stock = select(InventoryStocks).where(
            InventoryStocks.shop_id == reservation.shop_id,
            InventoryStocks.product_id == reservation.product_id,
            InventoryStocks.variant_id == reservation.variant_id,
            InventoryStocks.batch_id == reservation.batch_id
        ).with_for_update()

        serialno_infos=reservation.serialno_infos
        if serialno_infos:
            await ProductRepo(session=self.session).update_bulk_serialno(
                data=[
                    UpdateProductSerialnoDbSchema(
                        id=d['id'],
                        shop_id=reservation.shop_id,
                        status=ProductSerialnoStatusEnums.AVAILABLE
                    )
                    for d in serialno_infos
                ]
            )
        
        stock_record = (await self.session.execute(stmt_stock)).scalars().first()
        if stock_record:
            stock_record.reserved_stocks = max(0, (stock_record.reserved_stocks or 0) - reservation.qty)
            stock_record.available_stocks = stock_record.physical_stocks - stock_record.reserved_stocks
            
            readdb_res=await ProdInvReadDbRepo.add_updatereaddb(session=self.session,shop_id=reservation.shop_id,product_ids=[reservation.product_id])
            ic(readdb_res)
            
        reservation.status = "RELEASED"
            
        return True

    @start_db_transaction
    async def commit_reservations(self, data:CommitInventorySchema):
        stmt_res = select(InventoryReservation).where(
            InventoryReservation.session_id == data.session_id,
            InventoryReservation.status == "ACTIVE"
        ).with_for_update()
        
        reservations = (await self.session.execute(stmt_res)).scalars().all()
        
        product_ids=[]
        shop_id=None
        for res in reservations:
            # Update InventoryStocks with lock

            stmt_stock = select(InventoryStocks).where(
                InventoryStocks.shop_id == res.shop_id,
                InventoryStocks.product_id == res.product_id,
                InventoryStocks.variant_id == res.variant_id,
                InventoryStocks.batch_id == res.batch_id
            ).with_for_update()

            serialno_infos=res.serialno_infos
            if serialno_infos:
                await ProductRepo(session=self.session).delete_bulk_serialno(
                    data=[
                        d['id']
                        for d in serialno_infos
                    ]
                )
            
            stock_record = (await self.session.execute(stmt_stock)).scalars().first()
            stock_adj_mov_data=[]
            if stock_record:
                for resv in reservations:
                    ic(resv,data.model_dump())
                    stock_adj_mov_data.append(
                        {
                            "shop_id":resv.shop_id,
                            "product_id":resv.product_id,
                            "variant_id":resv.variant_id,
                            "batch_id":resv.batch_id,
                            "seriano_numbers":resv.serialno_infos,
                            "type":"DECREMENT",
                            "stocks":resv.qty,
                            "entity_name":data.entity_name
                        }
                    )

                
                # Apply delta to physical stocks (subtract because items are bought)
                stock_record.physical_stocks -= res.qty
                # Release reserved stock lock
                stock_record.reserved_stocks = max(0, (stock_record.reserved_stocks or 0) - abs(res.qty))
                stock_record.available_stocks = stock_record.physical_stocks - stock_record.reserved_stocks
                ic(stock_adj_mov_data)
                if data.record_stock:
                    stock_mov_adj_res=await emit_stock_mov_adj(session=self.session,data=stock_adj_mov_data)
                    ic(stock_mov_adj_res)

            product_ids.append(res.product_id) 
            ic(res.shop_id)
            shop_id=res.shop_id  
            res.status = "COMPLETED"
        
        readdb_res=await ProdInvReadDbRepo.add_updatereaddb(session=self.session,shop_id=shop_id,product_ids=product_ids)
        ic(readdb_res)
            
        return True