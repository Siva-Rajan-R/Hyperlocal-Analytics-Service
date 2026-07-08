from models.repo_models.base_repo_model import BaseRepoModel
from models.service_models.base_service_model import BaseServiceModel
from ..models.product_model import Products,ProductBatches,ProductSerialNumbers,ProductVariants
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select,update,delete,func,or_,and_,String,case,cast,Text,literal,literal_column,text,bindparam,null
from sqlalchemy.dialects.postgresql import JSONB,ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from schemas.v1.product_schemas.db_schemas import CreateProductBatchDbSchema,CreateProductDbSchema,CreateProductSerialnoDbSchema,CreateProductVariantDbSchema,UpdateProductBatchDbSchema,UpdateProductDbSchema,UpdateProductSerialnoDbSchema,UpdateProductVariantDbSchema,DeleteProductDbSchema
from schemas.v1.product_schemas.request_schemas import GetAllProductSchema,GetProductsById,GetProductsByShopId,VerifyCombinedSchema,GetBulkProductsById
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction
from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from typing import Optional,List
from icecream import ic
from core.data_formats.enums.stock_adj_enums import StockAdjustmentTypesEnum
from core.utils.prod_inv_unit_builder import build_inventory_units
from ..models.inventory_model import InventoryPricings,InventoryStocks,InventoryStoragelocations,InventoryReorderPoint
from collections import defaultdict






class ProductRepo:
    def __init__(self,session: AsyncSession):
        self.session=session
        self.product_cols=(
            Products.id,Products.name,Products.category_id,Products.ui_id,Products.shop_id,
            Products.unit_id,Products.description,Products.type_infos,Products.is_active,Products.gst,
            Products.have_tracking,Products.created_at,Products.updated_at,Products.additional_infos
        )
        self.variant_cols = (
            ProductVariants.id,
            ProductVariants.product_id,
            ProductVariants.name,
            ProductVariants.additional_infos,
            ProductVariants.created_at,
            ProductVariants.updated_at,
        )
        self.batch_cols = (
            ProductBatches.id,
            ProductBatches.product_id,
            ProductBatches.variant_id,
            ProductBatches.name,
            ProductBatches.expiration_infos,
            ProductBatches.additional_infos,
            ProductBatches.created_at,
            ProductBatches.updated_at,
        )
        self.serialno_cols = (
            ProductSerialNumbers.id,
            ProductSerialNumbers.product_id,
            ProductSerialNumbers.variant_id,
            ProductSerialNumbers.batch_id,
            ProductSerialNumbers.name,
            ProductSerialNumbers.status,
            ProductSerialNumbers.additional_infos,
            ProductSerialNumbers.created_at,
            ProductSerialNumbers.updated_at,
        )
        self.invetory_pricing_cols = (
            InventoryPricings.id,
            InventoryPricings.product_id,
            InventoryPricings.variant_id,
            InventoryPricings.batch_id,
            InventoryPricings.buy_price,
            InventoryPricings.sell_price,
            InventoryPricings.additional_infos,
            InventoryPricings.created_at,
            InventoryPricings.updated_at,
        )
        self.inventory_stl_cols = (
            InventoryStoragelocations.id,
            InventoryStoragelocations.product_id,
            InventoryStoragelocations.variant_id,
            InventoryStoragelocations.batch_id,
            InventoryStoragelocations.name,
            InventoryStoragelocations.additional_infos,
            InventoryStoragelocations.created_at,
            InventoryStoragelocations.updated_at,
        )
        self.inventory_stocks_cols = (
            InventoryStocks.id,
            InventoryStocks.product_id,
            InventoryStocks.variant_id,
            InventoryStocks.batch_id,
            InventoryStocks.physical_stocks,
            InventoryStocks.reserved_stocks,
            InventoryStocks.available_stocks,
            InventoryStocks.additional_infos,
            InventoryStocks.created_at,
            InventoryStocks.updated_at,
        )
        self.inventory_rop_cols = (
            InventoryReorderPoint.id,
            InventoryReorderPoint.product_id,
            InventoryReorderPoint.variant_id,
            InventoryReorderPoint.batch_id,
            InventoryReorderPoint.reorder_point,
            InventoryReorderPoint.additional_infos,
            InventoryReorderPoint.created_at,
            InventoryReorderPoint.updated_at,
        )

    @start_db_transaction
    async def create_product(self,data:CreateProductDbSchema):
        stmt=(
            insert(
                Products
            )
            .values(
                **data.model_dump(mode="json")
            )
            .returning(*self.product_cols)
        )

        res=(await self.session.execute(stmt)).mappings().one_or_none()
        ic(res)
        return res
    
    
    @start_db_transaction
    async def create_bulk_variant(self,data: List[ProductVariants]):
        if data:
            self.session.add_all(data)
        return True
    
    @start_db_transaction
    async def create_bulk_batch(self,data: List[ProductBatches]):
        if data:
            self.session.add_all(data)
        return True
    
    @start_db_transaction
    async def create_bulk_selialno(self,data: List[ProductSerialNumbers]):
        if data:
            self.session.add_all(data)
        return True

    @start_db_transaction
    async def update_bulk_product(self,data:List[UpdateProductDbSchema]):
        if not data:
            return True
        final_data=[d.model_dump(mode="json",exclude_none=True,exclude_unset=True) for d in data]
        res=(
            await self.session.run_sync(
                lambda session:session.bulk_update_mappings(
                    Products,
                    final_data
                )
            )
        )

        ic(res)
        return True
    

    @start_db_transaction
    async def update_bulk_variant(self,data:List[UpdateProductVariantDbSchema]):
        if not data:
            return True
        final_data=[d.model_dump(mode="json",exclude_none=True,exclude_unset=True) for d in data]
        res=(
            await self.session.run_sync(
                lambda session:session.bulk_update_mappings(
                    ProductVariants,
                    final_data
                )
            )
        )

        ic(res)
        return True
    

    @start_db_transaction
    async def update_bulk_batch(self,data:List[UpdateProductBatchDbSchema]):
        if not data:
            return True
        final_data=[d.model_dump(mode="json",exclude_none=True,exclude_unset=True) for d in data]
        res=(
            await self.session.run_sync(
                lambda session:session.bulk_update_mappings(
                    ProductBatches,
                    final_data
                )
            )
        )

        ic(res)
        return True
    

    # @start_db_transaction
    async def update_bulk_serialno(self,data:List[UpdateProductSerialnoDbSchema]):
        if not data:
            return True
        final_data=[d.model_dump(mode="json",exclude_none=True,exclude_unset=True) for d in data]
        res=(
            await self.session.run_sync(
                lambda session:session.bulk_update_mappings(
                    ProductSerialNumbers,
                    final_data
                )
            )
        )

        ic(res)
        return True

    
    @start_db_transaction
    async def delete_product(self,data:DeleteProductDbSchema):
        stmt=(
            delete(
                Products
            )
            .where(
                Products.id==data.id,
                Products.shop_id==data.shop_id
            )
            .returning(*self.product_cols)
        )

        res=(await self.session.execute(stmt)).scalar_one_or_none()
        ic(res)
        return res
    

    # @start_db_transaction
    async def delete_bulk_serialno(self,data:List[str]):
        stmt=(
            delete(
                ProductSerialNumbers
            )
            .where(
                ProductSerialNumbers.id.in_(data)
            )
            .returning(*self.serialno_cols)
        )

        res=(await self.session.execute(stmt)).scalars().all()
        ic(res)
        return res
    

    async def get_products(self, data: GetAllProductSchema):
        # 1. Handle Pagination
        offset = data.offset if data.offset > 0 else 1
        cursor = (offset - 1) * data.limit

        # 2. Build Query Statement
        stmt = (
            select(Products)
            .options(
                selectinload(Products.variants).load_only(*self.variant_cols),
                selectinload(Products.batches).load_only(*self.batch_cols),
                selectinload(Products.stocks).load_only(*self.inventory_stocks_cols),
                selectinload(Products.pricings).load_only(*self.invetory_pricing_cols),
                selectinload(Products.storage_locations).load_only(
                    *self.inventory_stl_cols
                ),
                selectinload(Products.reorder_points).load_only(
                    *self.inventory_rop_cols
                ),
            )
            .limit(data.limit)
            .offset(cursor)
        )

        if data.include_serialno:
            stmt = stmt.options(
                selectinload(Products.serialnos).load_only(*self.serialno_cols)
            )

        # 3. Execute Query
        res = (await self.session.execute(stmt)).scalars().all()
        final_res = []

        # 4. Map and Transform Database Rows
        for product in res:
            res_toadd = {
                "id": product.id,
                "shop_id": product.shop_id,
                "ui_id": product.ui_id,
                "name": product.name,
                "sku": product.sku,
                "barcode": product.barcode,
                "description": product.description,
                "category_id": product.category_id,
                "unit_id": product.unit_id,
                "is_active": product.is_active,
                "have_tracking": product.have_tracking,
                "created_at": product.created_at,
                "updated_at": product.updated_at,
                "type_infos": product.type_infos,
                "gst": product.gst,
            }

            # Build Lookups
            variant = {var.id: var for var in product.variants}

            # Multi-batch grouped by combined product_id + variant_id
            batches = defaultdict(list)
            for bat in product.batches:
                p_id = bat.product_id
                v_id = bat.variant_id or ""
                batches[p_id + v_id].append(bat)

            serialnos = defaultdict(list)
            if data.include_serialno:
                for serialno in product.serialnos:
                    p_id = serialno.product_id
                    v_id = serialno.variant_id or ""
                    b_id = serialno.batch_id or ""
                    serialnos[p_id + v_id + b_id].append(serialno)

            stocks = {}
            for stock in product.stocks:
                stocks[
                    (stock.product_id)
                    + (stock.variant_id or "")
                    + (stock.batch_id or "")
                ] = stock

            pricings = {}
            for price in product.pricings:
                pricings[
                    (price.product_id)
                    + (price.variant_id or "")
                    + (price.batch_id or "")
                ] = price

            rops = {}
            for rop in product.reorder_points:
                rops[
                    (rop.product_id)
                    + (rop.variant_id or "")
                    + (rop.batch_id or "")
                ] = rop

            stls = {}
            for stl in product.storage_locations:
                stls[
                    (stl.product_id)
                    + (stl.variant_id or "")
                    + (stl.batch_id or "")
                ] = stl

            # Flags for clean condition evaluations
            has_variant = product.type_infos.get("has_variant", False)
            has_batch = product.type_infos.get("has_batch", False)
            has_serialno = product.type_infos.get("has_serialno", False)

            # SITUATION A: Product Has Variants
            if has_variant:
                variant_infos = {}

                for key, val in variant.items():
                    variant_id = key
                    product_id = val.product_id
                    combined_id = product_id + variant_id

                    variant_infos[variant_id] = {
                        "name": val.name,
                        "batch_infos": [],
                        "serialno_infos": [],
                        "stock_infos": {},
                        "pricing_infos": {},
                        "reorder_point_infos": {},
                        "storage_location_infos": {},
                    }

                    # Resolve Batches if tracking exists
                    if has_batch:
                        product_batches = batches.get(combined_id, [])
                        for batch in product_batches:
                            final_key = combined_id + batch.id
                            
                            stock = stocks.get(final_key)
                            pricing = pricings.get(final_key)
                            rop = rops.get(final_key)
                            stl = stls.get(final_key)
                            sn_list = [
                                {"id": sn.id, "name": sn.name,"status":sn.status}
                                for sn in serialnos.get(final_key, [])
                            ]

                            b_info = {
                                "id": batch.id,
                                "name": batch.name,
                                "expiry_date": batch.expiration_infos.get("expiry_date") if batch.expiration_infos else None,
                                "manufacturing_date": batch.expiration_infos.get("manufacturing_date") if batch.expiration_infos else None,
                                "stock_infos": {
                                    "id": stock.id,
                                    "physical_stocks": stock.physical_stocks,
                                    "available_stocks": stock.available_stocks,
                                    "reserved_stocks": stock.reserved_stocks,
                                } if stock else {},
                                "storage_location_infos": {"id": stl.id, "storage_location": stl.name} if stl else {},
                                "reorder_point_infos": {"id": rop.id, "reorder_point": rop.reorder_point} if rop else {},
                                "pricing_infos": {
                                    "id": pricing.id,
                                    "sell_price": pricing.sell_price,
                                    "buy_price": pricing.buy_price,
                                } if pricing else {},
                                "serialno_infos": sn_list
                            }
                            variant_infos[variant_id]["batch_infos"].append(b_info)
                    
                    # Resolve No-Batch Variant Metrics
                    else:
                        final_key = combined_id + ""
                        stock = stocks.get(final_key)
                        pricing = pricings.get(final_key)
                        rop = rops.get(final_key)
                        stl = stls.get(final_key)
                        sn_list = [
                            {"id": sn.id, "name": sn.name,"status":sn.status}
                            for sn in serialnos.get(final_key, [])
                        ]

                        if has_serialno:
                            variant_infos[variant_id]["serialno_infos"] = sn_list
                        if stock:
                            variant_infos[variant_id]["stock_infos"] = {
                                "id": stock.id,
                                "physical_stocks": stock.physical_stocks,
                                "available_stocks": stock.available_stocks,
                                "reserved_stocks": stock.reserved_stocks
                            }
                        if pricing:
                            variant_infos[variant_id]["pricing_infos"] = {
                                "id": pricing.id,
                                "sell_price": pricing.sell_price,
                                "buy_price": pricing.buy_price,
                            }
                        if rop:
                            variant_infos[variant_id]["reorder_point_infos"] = {
                                "id": rop.id,
                                "reorder_point": rop.reorder_point,
                            }
                        if stl:
                            variant_infos[variant_id]["storage_location_infos"] = {
                                "id": stl.id,
                                "storage_location": stl.name,
                            }

                res_toadd["variants"] = variant_infos

            # SITUATION B: Standard Product (No Variants)
            else:
                batch_infos = []
                serialno_infos = []
                stock_infos = {}
                pricing_infos = {}
                reorder_point_infos = {}
                storage_location_infos = {}

                variant_id = ""
                product_id = product.id
                combined_id = product_id + variant_id

                if has_batch:
                    product_batches = batches.get(combined_id, [])
                    for batch in product_batches:
                        final_key = combined_id + batch.id
                        
                        stock = stocks.get(final_key)
                        pricing = pricings.get(final_key)
                        rop = rops.get(final_key)
                        stl = stls.get(final_key)
                        sn_list = [
                            {"id": sn.id, "name": sn.name,"status":sn.status}
                            for sn in serialnos.get(final_key, [])
                        ]

                        b_info = {
                            "id": batch.id,
                            "name": batch.name,
                            "expiry_date": batch.expiration_infos.get("expiry_date") if batch.expiration_infos else None,
                            "manufacturing_date": batch.expiration_infos.get("manufacturing_date") if batch.expiration_infos else None,
                            "stock_infos": {
                                "id": stock.id,
                                "physical_stocks": stock.physical_stocks,
                                "available_stocks": stock.available_stocks,
                                "reserved_stocks": stock.reserved_stocks,
                            } if stock else {},
                            "storage_location_infos": {"id": stl.id, "storage_location": stl.name} if stl else {},
                            "reorder_point_infos": {"id": rop.id, "reorder_point": rop.reorder_point} if rop else {},
                            "pricing_infos": {
                                "id": pricing.id,
                                "sell_price": pricing.sell_price,
                                "buy_price": pricing.buy_price,
                            } if pricing else {},
                            "serialno_infos": sn_list
                        }
                        batch_infos.append(b_info)
                else:
                    final_key = combined_id + ""
                    stock = stocks.get(final_key)
                    pricing = pricings.get(final_key)
                    rop = rops.get(final_key)
                    stl = stls.get(final_key)
                    sn_list = [
                        {"id": sn.id, "name": sn.name,"status":sn.status}
                        for sn in serialnos.get(final_key, [])
                    ]

                    if has_serialno:
                        serialno_infos = sn_list
                    if stock:
                        stock_infos = {
                            "id": stock.id,
                            "physical_stocks": stock.physical_stocks,
                            "available_stocks": stock.available_stocks,
                            "reserved_stocks": stock.reserved_stocks,
                        }
                    if pricing:
                        pricing_infos = {
                            "id": pricing.id,
                            "sell_price": pricing.sell_price,
                            "buy_price": pricing.buy_price,
                        }
                    if rop:
                        reorder_point_infos = {
                            "id": rop.id,
                            "reorder_point": rop.reorder_point,
                        }
                    if stl:
                        storage_location_infos = {
                            "id": stl.id,
                            "storage_location": stl.name,
                        }

                res_toadd.update(
                    {
                        "batch_infos": batch_infos,
                        "serialno_infos": serialno_infos,
                        "stock_infos": stock_infos,
                        "pricing_infos": pricing_infos,
                        "reorder_point_infos": reorder_point_infos,
                        "storage_location_infos": storage_location_infos,
                    }
                )

            final_res.append(res_toadd)

        return final_res
    

    async def get_products_by_shop_id(self,data:GetProductsByShopId):
        offset=data.offset if data.offset>0 else 1
        cursor=(offset-1)*data.limit

        stmt = (
            select(Products)
            .where(Products.shop_id==data.shop_id)
            .options(
                selectinload(Products.variants).load_only(*self.variant_cols),

                selectinload(Products.batches).load_only(*self.batch_cols),

                selectinload(Products.stocks).load_only(*self.inventory_stocks_cols),

                selectinload(Products.pricings).load_only(*self.invetory_pricing_cols),

                selectinload(Products.storage_locations).load_only(*self.inventory_stl_cols),

                selectinload(Products.reorder_points).load_only(*self.inventory_rop_cols),
            )
            .limit(data.limit)
            .offset(cursor)
        )

        if data.include_serialno:
            stmt = stmt.options(
                selectinload(Products.serialnos).load_only(*self.serialno_cols)
            )

        res = (await self.session.execute(stmt)).scalars().all()
        final_res = []

        # 4. Map and Transform Database Rows
        for product in res:
            res_toadd = {
                "id": product.id,
                "shop_id": product.shop_id,
                "ui_id": product.ui_id,
                "name": product.name,
                "sku": product.sku,
                "barcode": product.barcode,
                "description": product.description,
                "category_id": product.category_id,
                "unit_id": product.unit_id,
                "is_active": product.is_active,
                "have_tracking": product.have_tracking,
                "created_at": product.created_at,
                "updated_at": product.updated_at,
                "type_infos": product.type_infos,
                "gst": product.gst,
            }

            # Build Lookups
            variant = {var.id: var for var in product.variants}

            # Multi-batch grouped by combined product_id + variant_id
            batches = defaultdict(list)
            for bat in product.batches:
                p_id = bat.product_id
                v_id = bat.variant_id or ""
                batches[p_id + v_id].append(bat)

            serialnos = defaultdict(list)
            if data.include_serialno:
                for serialno in product.serialnos:
                    p_id = serialno.product_id
                    v_id = serialno.variant_id or ""
                    b_id = serialno.batch_id or ""
                    serialnos[p_id + v_id + b_id].append(serialno)

            stocks = {}
            for stock in product.stocks:
                stocks[
                    (stock.product_id)
                    + (stock.variant_id or "")
                    + (stock.batch_id or "")
                ] = stock

            pricings = {}
            for price in product.pricings:
                pricings[
                    (price.product_id)
                    + (price.variant_id or "")
                    + (price.batch_id or "")
                ] = price

            rops = {}
            for rop in product.reorder_points:
                rops[
                    (rop.product_id)
                    + (rop.variant_id or "")
                    + (rop.batch_id or "")
                ] = rop

            stls = {}
            for stl in product.storage_locations:
                stls[
                    (stl.product_id)
                    + (stl.variant_id or "")
                    + (stl.batch_id or "")
                ] = stl

            # Flags for clean condition evaluations
            has_variant = product.type_infos.get("has_variant", False)
            has_batch = product.type_infos.get("has_batch", False)
            has_serialno = product.type_infos.get("has_serialno", False)

            # SITUATION A: Product Has Variants
            if has_variant:
                variant_infos = {}

                for key, val in variant.items():
                    variant_id = key
                    product_id = val.product_id
                    combined_id = product_id + variant_id

                    variant_infos[variant_id] = {
                        "name": val.name,
                        "batch_infos": [],
                        "serialno_infos": [],
                        "stock_infos": {},
                        "pricing_infos": {},
                        "reorder_point_infos": {},
                        "storage_location_infos": {},
                    }

                    # Resolve Batches if tracking exists
                    if has_batch:
                        product_batches = batches.get(combined_id, [])
                        for batch in product_batches:
                            final_key = combined_id + batch.id
                            
                            stock = stocks.get(final_key)
                            pricing = pricings.get(final_key)
                            rop = rops.get(final_key)
                            stl = stls.get(final_key)
                            sn_list = [
                                {"id": sn.id, "name": sn.name,"status":sn.status}
                                for sn in serialnos.get(final_key, [])
                            ]

                            b_info = {
                                "id": batch.id,
                                "name": batch.name,
                                "expiry_date": batch.expiration_infos.get("expiry_date") if batch.expiration_infos else None,
                                "manufacturing_date": batch.expiration_infos.get("manufacturing_date") if batch.expiration_infos else None,
                                "stock_infos": {
                                    "id": stock.id,
                                    "physical_stocks": stock.physical_stocks,
                                    "available_stocks": stock.available_stocks,
                                    "reserved_stocks": stock.reserved_stocks,
                                } if stock else {},
                                "storage_location_infos": {"id": stl.id, "storage_location": stl.name} if stl else {},
                                "reorder_point_infos": {"id": rop.id, "reorder_point": rop.reorder_point} if rop else {},
                                "pricing_infos": {
                                    "id": pricing.id,
                                    "sell_price": pricing.sell_price,
                                    "buy_price": pricing.buy_price,
                                } if pricing else {},
                                "serialno_infos": sn_list
                            }
                            variant_infos[variant_id]["batch_infos"].append(b_info)
                    
                    # Resolve No-Batch Variant Metrics
                    else:
                        final_key = combined_id + ""
                        stock = stocks.get(final_key)
                        pricing = pricings.get(final_key)
                        rop = rops.get(final_key)
                        stl = stls.get(final_key)
                        sn_list = [
                            {"id": sn.id, "name": sn.name,"status":sn.status}
                            for sn in serialnos.get(final_key, [])
                        ]

                        if has_serialno:
                            variant_infos[variant_id]["serialno_infos"] = sn_list
                        if stock:
                            variant_infos[variant_id]["stock_infos"] = {
                                "id": stock.id,
                                "physical_stocks": stock.physical_stocks,
                                "available_stocks": stock.available_stocks,
                                "reserved_stocks": stock.reserved_stocks
                            }
                        if pricing:
                            variant_infos[variant_id]["pricing_infos"] = {
                                "id": pricing.id,
                                "sell_price": pricing.sell_price,
                                "buy_price": pricing.buy_price,
                            }
                        if rop:
                            variant_infos[variant_id]["reorder_point_infos"] = {
                                "id": rop.id,
                                "reorder_point": rop.reorder_point,
                            }
                        if stl:
                            variant_infos[variant_id]["storage_location_infos"] = {
                                "id": stl.id,
                                "storage_location": stl.name,
                            }

                res_toadd["variants"] = variant_infos

            # SITUATION B: Standard Product (No Variants)
            else:
                batch_infos = []
                serialno_infos = []
                stock_infos = {}
                pricing_infos = {}
                reorder_point_infos = {}
                storage_location_infos = {}

                variant_id = ""
                product_id = product.id
                combined_id = product_id + variant_id

                if has_batch:
                    product_batches = batches.get(combined_id, [])
                    for batch in product_batches:
                        final_key = combined_id + batch.id
                        
                        stock = stocks.get(final_key)
                        pricing = pricings.get(final_key)
                        rop = rops.get(final_key)
                        stl = stls.get(final_key)
                        sn_list = [
                            {"id": sn.id, "name": sn.name,"status":sn.status}
                            for sn in serialnos.get(final_key, [])
                        ]

                        b_info = {
                            "id": batch.id,
                            "name": batch.name,
                            "expiry_date": batch.expiration_infos.get("expiry_date") if batch.expiration_infos else None,
                            "manufacturing_date": batch.expiration_infos.get("manufacturing_date") if batch.expiration_infos else None,
                            "stock_infos": {
                                "id": stock.id,
                                "physical_stocks": stock.physical_stocks,
                                "available_stocks": stock.available_stocks,
                                "reserved_stocks": stock.reserved_stocks,
                            } if stock else {},
                            "storage_location_infos": {"id": stl.id, "storage_location": stl.name} if stl else {},
                            "reorder_point_infos": {"id": rop.id, "reorder_point": rop.reorder_point} if rop else {},
                            "pricing_infos": {
                                "id": pricing.id,
                                "sell_price": pricing.sell_price,
                                "buy_price": pricing.buy_price,
                            } if pricing else {},
                            "serialno_infos": sn_list
                        }
                        batch_infos.append(b_info)
                else:
                    final_key = combined_id + ""
                    stock = stocks.get(final_key)
                    pricing = pricings.get(final_key)
                    rop = rops.get(final_key)
                    stl = stls.get(final_key)
                    sn_list = [
                        {"id": sn.id, "name": sn.name,"status":sn.status}
                        for sn in serialnos.get(final_key, [])
                    ]

                    if has_serialno:
                        serialno_infos = sn_list
                    if stock:
                        stock_infos = {
                            "id": stock.id,
                            "physical_stocks": stock.physical_stocks,
                            "available_stocks": stock.available_stocks,
                            "reserved_stocks": stock.reserved_stocks,
                        }
                    if pricing:
                        pricing_infos = {
                            "id": pricing.id,
                            "sell_price": pricing.sell_price,
                            "buy_price": pricing.buy_price,
                        }
                    if rop:
                        reorder_point_infos = {
                            "id": rop.id,
                            "reorder_point": rop.reorder_point,
                        }
                    if stl:
                        storage_location_infos = {
                            "id": stl.id,
                            "storage_location": stl.name,
                        }

                res_toadd.update(
                    {
                        "batch_infos": batch_infos,
                        "serialno_infos": serialno_infos,
                        "stock_infos": stock_infos,
                        "pricing_infos": pricing_infos,
                        "reorder_point_infos": reorder_point_infos,
                        "storage_location_infos": storage_location_infos,
                    }
                )

            final_res.append(res_toadd)

        return final_res
    

    async def get_products_by_id(self,data:GetProductsById):
        stmt = (
            select(Products)
            .where(Products.shop_id==data.shop_id,Products.id==data.id)
            .options(
                selectinload(Products.variants).load_only(*self.variant_cols),

                selectinload(Products.batches).load_only(*self.batch_cols),

                selectinload(Products.stocks).load_only(*self.inventory_stocks_cols),

                selectinload(Products.pricings).load_only(*self.invetory_pricing_cols),

                selectinload(Products.storage_locations).load_only(*self.inventory_stl_cols),

                selectinload(Products.reorder_points).load_only(*self.inventory_rop_cols),
            )
        )

        if data.include_serialno:
            stmt=stmt.options(selectinload(Products.serialnos).load_only(*self.serialno_cols))

        # 3. Execute Query
        res = (await self.session.execute(stmt)).scalars().one_or_none()
        final_res = []

        # 4. Map and Transform Database Rows
        for product in [res]:
            res_toadd = {
                "id": product.id,
                "shop_id": product.shop_id,
                "ui_id": product.ui_id,
                "name": product.name,
                "sku": product.sku,
                "barcode": product.barcode,
                "description": product.description,
                "category_id": product.category_id,
                "unit_id": product.unit_id,
                "is_active": product.is_active,
                "have_tracking": product.have_tracking,
                "created_at": product.created_at,
                "updated_at": product.updated_at,
                "type_infos": product.type_infos,
                "gst": product.gst,
            }

            # Build Lookups
            variant = {var.id: var for var in product.variants}

            # Multi-batch grouped by combined product_id + variant_id
            batches = defaultdict(list)
            for bat in product.batches:
                p_id = bat.product_id
                v_id = bat.variant_id or ""
                batches[p_id + v_id].append(bat)

            serialnos = defaultdict(list)
            if data.include_serialno:
                for serialno in product.serialnos:
                    p_id = serialno.product_id
                    v_id = serialno.variant_id or ""
                    b_id = serialno.batch_id or ""
                    serialnos[p_id + v_id + b_id].append(serialno)

            stocks = {}
            for stock in product.stocks:
                stocks[
                    (stock.product_id)
                    + (stock.variant_id or "")
                    + (stock.batch_id or "")
                ] = stock

            pricings = {}
            for price in product.pricings:
                pricings[
                    (price.product_id)
                    + (price.variant_id or "")
                    + (price.batch_id or "")
                ] = price

            rops = {}
            for rop in product.reorder_points:
                rops[
                    (rop.product_id)
                    + (rop.variant_id or "")
                    + (rop.batch_id or "")
                ] = rop

            stls = {}
            for stl in product.storage_locations:
                stls[
                    (stl.product_id)
                    + (stl.variant_id or "")
                    + (stl.batch_id or "")
                ] = stl

            # Flags for clean condition evaluations
            has_variant = product.type_infos.get("has_variant", False)
            has_batch = product.type_infos.get("has_batch", False)
            has_serialno = product.type_infos.get("has_serialno", False)

            # SITUATION A: Product Has Variants
            if has_variant:
                variant_infos = {}

                for key, val in variant.items():
                    variant_id = key
                    product_id = val.product_id
                    combined_id = product_id + variant_id

                    variant_infos[variant_id] = {
                        "name": val.name,
                        "batch_infos": [],
                        "serialno_infos": [],
                        "stock_infos": {},
                        "pricing_infos": {},
                        "reorder_point_infos": {},
                        "storage_location_infos": {},
                    }

                    # Resolve Batches if tracking exists
                    if has_batch:
                        product_batches = batches.get(combined_id, [])
                        for batch in product_batches:
                            final_key = combined_id + batch.id
                            
                            stock = stocks.get(final_key)
                            pricing = pricings.get(final_key)
                            rop = rops.get(final_key)
                            stl = stls.get(final_key)
                            sn_list = [
                                {"id": sn.id, "name": sn.name,"status":sn.status}
                                for sn in serialnos.get(final_key, [])
                            ]

                            b_info = {
                                "id": batch.id,
                                "name": batch.name,
                                "expiry_date": batch.expiration_infos.get("expiry_date") if batch.expiration_infos else None,
                                "manufacturing_date": batch.expiration_infos.get("manufacturing_date") if batch.expiration_infos else None,
                                "stock_infos": {
                                    "id": stock.id,
                                    "physical_stocks": stock.physical_stocks,
                                    "available_stocks": stock.available_stocks,
                                    "reserved_stocks": stock.reserved_stocks,
                                } if stock else {},
                                "storage_location_infos": {"id": stl.id, "storage_location": stl.name} if stl else {},
                                "reorder_point_infos": {"id": rop.id, "reorder_point": rop.reorder_point} if rop else {},
                                "pricing_infos": {
                                    "id": pricing.id,
                                    "sell_price": pricing.sell_price,
                                    "buy_price": pricing.buy_price,
                                } if pricing else {},
                                "serialno_infos": sn_list
                            }
                            variant_infos[variant_id]["batch_infos"].append(b_info)
                    
                    # Resolve No-Batch Variant Metrics
                    else:
                        final_key = combined_id + ""
                        stock = stocks.get(final_key)
                        pricing = pricings.get(final_key)
                        rop = rops.get(final_key)
                        stl = stls.get(final_key)
                        sn_list = [
                            {"id": sn.id, "name": sn.name,"status":sn.status}
                            for sn in serialnos.get(final_key, [])
                        ]

                        if has_serialno:
                            variant_infos[variant_id]["serialno_infos"] = sn_list
                        if stock:
                            variant_infos[variant_id]["stock_infos"] = {
                                "id": stock.id,
                                "physical_stocks": stock.physical_stocks,
                                "available_stocks": stock.available_stocks,
                                "reserved_stocks": stock.reserved_stocks,
                            }
                        if pricing:
                            variant_infos[variant_id]["pricing_infos"] = {
                                "id": pricing.id,
                                "sell_price": pricing.sell_price,
                                "buy_price": pricing.buy_price,
                            }
                        if rop:
                            variant_infos[variant_id]["reorder_point_infos"] = {
                                "id": rop.id,
                                "reorder_point": rop.reorder_point,
                            }
                        if stl:
                            variant_infos[variant_id]["storage_location_infos"] = {
                                "id": stl.id,
                                "storage_location": stl.name,
                            }

                res_toadd["variants"] = variant_infos

            # SITUATION B: Standard Product (No Variants)
            else:
                batch_infos = []
                serialno_infos = []
                stock_infos = {}
                pricing_infos = {}
                reorder_point_infos = {}
                storage_location_infos = {}

                variant_id = ""
                product_id = product.id
                combined_id = product_id + variant_id

                if has_batch:
                    product_batches = batches.get(combined_id, [])
                    for batch in product_batches:
                        final_key = combined_id + batch.id
                        
                        stock = stocks.get(final_key)
                        pricing = pricings.get(final_key)
                        rop = rops.get(final_key)
                        stl = stls.get(final_key)
                        sn_list = [
                            {"id": sn.id, "name": sn.name,"status":sn.status}
                            for sn in serialnos.get(final_key, [])
                        ]

                        b_info = {
                            "id": batch.id,
                            "name": batch.name,
                            "expiry_date": batch.expiration_infos.get("expiry_date") if batch.expiration_infos else None,
                            "manufacturing_date": batch.expiration_infos.get("manufacturing_date") if batch.expiration_infos else None,
                            "stock_infos": {
                                "id": stock.id,
                                "physical_stocks": stock.physical_stocks,
                                "available_stocks": stock.available_stocks,
                                "reserved_stocks": stock.reserved_stocks,
                            } if stock else {},
                            "storage_location_infos": {"id": stl.id, "storage_location": stl.name} if stl else {},
                            "reorder_point_infos": {"id": rop.id, "reorder_point": rop.reorder_point} if rop else {},
                            "pricing_infos": {
                                "id": pricing.id,
                                "sell_price": pricing.sell_price,
                                "buy_price": pricing.buy_price,
                            } if pricing else {},
                            "serialno_infos": sn_list
                        }
                        batch_infos.append(b_info)
                else:
                    final_key = combined_id + ""
                    stock = stocks.get(final_key)
                    pricing = pricings.get(final_key)
                    rop = rops.get(final_key)
                    stl = stls.get(final_key)
                    sn_list = [
                        {"id": sn.id, "name": sn.name,"status":sn.status}
                        for sn in serialnos.get(final_key, [])
                    ]

                    if has_serialno:
                        serialno_infos = sn_list
                    if stock:
                        stock_infos = {
                            "id": stock.id,
                            "physical_stocks": stock.physical_stocks,
                            "available_stocks": stock.available_stocks,
                            "reserved_stocks": stock.reserved_stocks,
                        }
                    if pricing:
                        pricing_infos = {
                            "id": pricing.id,
                            "sell_price": pricing.sell_price,
                            "buy_price": pricing.buy_price,
                        }
                    if rop:
                        reorder_point_infos = {
                            "id": rop.id,
                            "reorder_point": rop.reorder_point,
                        }
                    if stl:
                        storage_location_infos = {
                            "id": stl.id,
                            "storage_location": stl.name,
                        }

                res_toadd.update(
                    {
                        "batch_infos": batch_infos,
                        "serialno_infos": serialno_infos,
                        "stock_infos": stock_infos,
                        "pricing_infos": pricing_infos,
                        "reorder_point_infos": reorder_point_infos,
                        "storage_location_infos": storage_location_infos,
                    }
                )

            final_res.append(res_toadd)

        return final_res[0]


    async def get_bulk_products_by_id(self,data:GetBulkProductsById):
        stmt = (
            select(Products)
            .where(Products.shop_id==data.shop_id,Products.id.in_(data.id))
            .options(
                selectinload(Products.variants).load_only(*self.variant_cols),

                selectinload(Products.batches).load_only(*self.batch_cols),

                selectinload(Products.stocks).load_only(*self.inventory_stocks_cols),

                selectinload(Products.pricings).load_only(*self.invetory_pricing_cols),

                selectinload(Products.storage_locations).load_only(*self.inventory_stl_cols),

                selectinload(Products.reorder_points).load_only(*self.inventory_rop_cols),
            )
        )

        if data.include_serialno:
            stmt=stmt.options(selectinload(Products.serialnos).load_only(*self.serialno_cols))

        # 3. Execute Query
        res = (await self.session.execute(stmt)).scalars().all()
        final_res = []

        # 4. Map and Transform Database Rows
        for product in res:
            res_toadd = {
                "id": product.id,
                "shop_id": product.shop_id,
                "ui_id": product.ui_id,
                "name": product.name,
                "sku": product.sku,
                "barcode": product.barcode,
                "description": product.description,
                "category_id": product.category_id,
                "unit_id": product.unit_id,
                "is_active": product.is_active,
                "have_tracking": product.have_tracking,
                "created_at": product.created_at,
                "updated_at": product.updated_at,
                "type_infos": product.type_infos,
                "gst": product.gst,
            }

            # Build Lookups
            variant = {var.id: var for var in product.variants}

            # Multi-batch grouped by combined product_id + variant_id
            batches = defaultdict(list)
            for bat in product.batches:
                p_id = bat.product_id
                v_id = bat.variant_id or ""
                batches[p_id + v_id].append(bat)

            serialnos = defaultdict(list)
            if data.include_serialno:
                for serialno in product.serialnos:
                    p_id = serialno.product_id
                    v_id = serialno.variant_id or ""
                    b_id = serialno.batch_id or ""
                    serialnos[p_id + v_id + b_id].append(serialno)

            stocks = {}
            for stock in product.stocks:
                stocks[
                    (stock.product_id)
                    + (stock.variant_id or "")
                    + (stock.batch_id or "")
                ] = stock

            pricings = {}
            for price in product.pricings:
                pricings[
                    (price.product_id)
                    + (price.variant_id or "")
                    + (price.batch_id or "")
                ] = price

            rops = {}
            for rop in product.reorder_points:
                rops[
                    (rop.product_id)
                    + (rop.variant_id or "")
                    + (rop.batch_id or "")
                ] = rop

            stls = {}
            for stl in product.storage_locations:
                stls[
                    (stl.product_id)
                    + (stl.variant_id or "")
                    + (stl.batch_id or "")
                ] = stl

            # Flags for clean condition evaluations
            has_variant = product.type_infos.get("has_variant", False)
            has_batch = product.type_infos.get("has_batch", False)
            has_serialno = product.type_infos.get("has_serialno", False)

            # SITUATION A: Product Has Variants
            if has_variant:
                variant_infos = {}

                for key, val in variant.items():
                    variant_id = key
                    product_id = val.product_id
                    combined_id = product_id + variant_id

                    variant_infos[variant_id] = {
                        "name": val.name,
                        "batch_infos": [],
                        "serialno_infos": [],
                        "stock_infos": {},
                        "pricing_infos": {},
                        "reorder_point_infos": {},
                        "storage_location_infos": {},
                    }

                    # Resolve Batches if tracking exists
                    if has_batch:
                        product_batches = batches.get(combined_id, [])
                        for batch in product_batches:
                            final_key = combined_id + batch.id
                            
                            stock = stocks.get(final_key)
                            pricing = pricings.get(final_key)
                            rop = rops.get(final_key)
                            stl = stls.get(final_key)
                            sn_list = [
                                {"id": sn.id, "name": sn.name,"status":sn.status}
                                for sn in serialnos.get(final_key, [])
                            ]

                            b_info = {
                                "id": batch.id,
                                "name": batch.name,
                                "expiry_date": batch.expiration_infos.get("expiry_date") if batch.expiration_infos else None,
                                "manufacturing_date": batch.expiration_infos.get("manufacturing_date") if batch.expiration_infos else None,
                                "stock_infos": {
                                    "id": stock.id,
                                    "physical_stocks": stock.physical_stocks,
                                    "available_stocks": stock.available_stocks,
                                    "reserved_stocks": stock.reserved_stocks,
                                } if stock else {},
                                "storage_location_infos": {"id": stl.id, "storage_location": stl.name} if stl else {},
                                "reorder_point_infos": {"id": rop.id, "reorder_point": rop.reorder_point} if rop else {},
                                "pricing_infos": {
                                    "id": pricing.id,
                                    "sell_price": pricing.sell_price,
                                    "buy_price": pricing.buy_price,
                                } if pricing else {},
                                "serialno_infos": sn_list
                            }
                            variant_infos[variant_id]["batch_infos"].append(b_info)
                    
                    # Resolve No-Batch Variant Metrics
                    else:
                        final_key = combined_id + ""
                        stock = stocks.get(final_key)
                        pricing = pricings.get(final_key)
                        rop = rops.get(final_key)
                        stl = stls.get(final_key)
                        sn_list = [
                            {"id": sn.id, "name": sn.name,"status":sn.status}
                            for sn in serialnos.get(final_key, [])
                        ]

                        if has_serialno:
                            variant_infos[variant_id]["serialno_infos"] = sn_list
                        if stock:
                            variant_infos[variant_id]["stock_infos"] = {
                                "id": stock.id,
                                "physical_stocks": stock.physical_stocks,
                                "available_stocks": stock.available_stocks,
                                "reserved_stocks": stock.reserved_stocks
                            }
                        if pricing:
                            variant_infos[variant_id]["pricing_infos"] = {
                                "id": pricing.id,
                                "sell_price": pricing.sell_price,
                                "buy_price": pricing.buy_price,
                            }
                        if rop:
                            variant_infos[variant_id]["reorder_point_infos"] = {
                                "id": rop.id,
                                "reorder_point": rop.reorder_point,
                            }
                        if stl:
                            variant_infos[variant_id]["storage_location_infos"] = {
                                "id": stl.id,
                                "storage_location": stl.name,
                            }

                res_toadd["variants"] = variant_infos

            # SITUATION B: Standard Product (No Variants)
            else:
                batch_infos = []
                serialno_infos = []
                stock_infos = {}
                pricing_infos = {}
                reorder_point_infos = {}
                storage_location_infos = {}

                variant_id = ""
                product_id = product.id
                combined_id = product_id + variant_id

                if has_batch:
                    product_batches = batches.get(combined_id, [])
                    for batch in product_batches:
                        final_key = combined_id + batch.id
                        
                        stock = stocks.get(final_key)
                        pricing = pricings.get(final_key)
                        rop = rops.get(final_key)
                        stl = stls.get(final_key)
                        sn_list = [
                            {"id": sn.id, "name": sn.name,"status":sn.status}
                            for sn in serialnos.get(final_key, [])
                        ]

                        b_info = {
                            "id": batch.id,
                            "name": batch.name,
                            "expiry_date": batch.expiration_infos.get("expiry_date") if batch.expiration_infos else None,
                            "manufacturing_date": batch.expiration_infos.get("manufacturing_date") if batch.expiration_infos else None,
                            "stock_infos": {
                                "id": stock.id,
                                "physical_stocks": stock.physical_stocks,
                                "available_stocks": stock.available_stocks,
                                "reserved_stocks": stock.reserved_stocks,
                            } if stock else {},
                            "storage_location_infos": {"id": stl.id, "storage_location": stl.name} if stl else {},
                            "reorder_point_infos": {"id": rop.id, "reorder_point": rop.reorder_point} if rop else {},
                            "pricing_infos": {
                                "id": pricing.id,
                                "sell_price": pricing.sell_price,
                                "buy_price": pricing.buy_price,
                            } if pricing else {},
                            "serialno_infos": sn_list
                        }
                        batch_infos.append(b_info)
                else:
                    final_key = combined_id + ""
                    stock = stocks.get(final_key)
                    pricing = pricings.get(final_key)
                    rop = rops.get(final_key)
                    stl = stls.get(final_key)
                    sn_list = [
                        {"id": sn.id, "name": sn.name,"status":sn.status}
                        for sn in serialnos.get(final_key, [])
                    ]

                    if has_serialno:
                        serialno_infos = sn_list
                    if stock:
                        stock_infos = {
                            "id": stock.id,
                            "physical_stocks": stock.physical_stocks,
                            "available_stocks": stock.available_stocks,
                            "reserved_stocks": stock.reserved_stocks,
                        }
                    if pricing:
                        pricing_infos = {
                            "id": pricing.id,
                            "sell_price": pricing.sell_price,
                            "buy_price": pricing.buy_price,
                        }
                    if rop:
                        reorder_point_infos = {
                            "id": rop.id,
                            "reorder_point": rop.reorder_point,
                        }
                    if stl:
                        storage_location_infos = {
                            "id": stl.id,
                            "storage_location": stl.name,
                        }

                res_toadd.update(
                    {
                        "batch_infos": batch_infos,
                        "serialno_infos": serialno_infos,
                        "stock_infos": stock_infos,
                        "pricing_infos": pricing_infos,
                        "reorder_point_infos": reorder_point_infos,
                        "storage_location_infos": storage_location_infos,
                    }
                )

            final_res.append(res_toadd)

        return final_res
    

    
    


    async def verify_bulk_product(self,data: List[str]):
        stmt=(
            select(
                *self.product_cols
            )
            .where(
                Products.id.in_(data)
            )
        )

        res=(await self.session.execute(stmt)).mappings().all()
        ic(res)
        return res
    

    async def verify_bulk_variant(self,data: List[str]):
        stmt=(
            select(
                *self.variant_cols
            )
            .where(
                ProductVariants.id.in_(data)
            )
        )

        res=(await self.session.execute(stmt)).mappings().all()
        ic(res)
        return res
    

    async def verify_bulk_batch(self,data: List[str]):
        stmt=(
            select(
                *self.batch_cols
            )
            .where(
                ProductBatches.id.in_(data)
            )
        )

        res=(await self.session.execute(stmt)).mappings().all()
        ic(res)
        return res
    
    async def verify_bulk_serialno(self,data: List[str]):
        stmt=(
            select(
                *self.serialno_cols
            )
            .where(
                ProductSerialNumbers.id.in_(data)
            )
        )

        res=(await self.session.execute(stmt)).mappings().all()
        ic(res)
        return res
    

    async def verify_bulk_serialno_name(self,data: List[dict]):
        stmt=(
            select(
                ProductSerialNumbers.id
            )
            .where(
                ProductSerialNumbers.shop_id==bindparam("shop_id"),
                ProductSerialNumbers.product_id==bindparam("product_id"),
                ProductSerialNumbers.variant_id.is_not_distinct_from(bindparam("variant_id")),
                ProductSerialNumbers.batch_id.is_not_distinct_from(bindparam("batch_id")),
                ProductSerialNumbers.name.in_(bindparam("names",expanding=True))
            )
        )

        res=(
            await self.session.execute(
                stmt,
                [
                    {
                        'shop_id':d['shop_id'],
                        'product_id':d['product_id'],
                        'variant_id':d['variant_id'],
                        'batch_id':d['batch_id'],
                        'names':d['names']
                    }
                    for d in data
                ]
            )
        ).mappings().all()
        ic(res)
        return res
    

    async def verify_bulk_batch_name(self,data: List[dict]):
        stmt=(
            select(
                ProductBatches.id
            )
            .where(
                ProductBatches.shop_id==bindparam("shop_id"),
                ProductBatches.product_id==bindparam("product_id"),
                ProductBatches.variant_id.is_not_distinct_from(bindparam("variant_id")),
                ProductBatches.name.in_(bindparam("names",expanding=True))
            )
        )

        res=(
            await self.session.execute(
                stmt,
                [
                    {
                        'shop_id':d['shop_id'],
                        'product_id':d['product_id'],
                        'variant_id':d['variant_id'],
                        'names':d['names']
                    }
                    for d in data
                ]
            )
        ).mappings().all()
        ic(res)
        return res
    

    async def verify_combined(self,data:VerifyCombinedSchema):
        products=[]
        variants=[]
        batches=[]
        serialnos=[]
        
        if data.products:
           res=await self.verify_bulk_product(data=data.products)
           ic(res)
           products.extend(res)

        if data.variants:
           res=await self.verify_bulk_variant(data=data.variants)
           ic(res)
           variants.extend(res)

        if data.batches:
           res=await self.verify_bulk_batch(data=data.batches)
           ic(res)
           batches.extend(res)

        if data.serialnos:
            res=await self.verify_bulk_serialno(data=data.serialnos)
            ic(res)
            serialnos.extend(res)
        


        return {
            "products":products,
            "variants":variants,
            "batches":batches,
            "serialnos":serialnos
        }
    
    
        