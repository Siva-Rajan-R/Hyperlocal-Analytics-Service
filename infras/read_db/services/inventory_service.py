from ..repos.base_repo import ReadDbBaseRepo
from ..main import INVENTORY_COLLECTION
from typing import Optional,List,Any
from models.infra_models.readdb_model import BaseReadDbModel
from pymongo import UpdateOne
from ..models.supplier_model import InventoryReadModel
from ..models.prod_inv_model import ProdInvReadModel
from icecream import ic


class ReadDbInventoryService(BaseReadDbModel):
    def __init__(self,payload:Any=None,conditions:dict=None):
        self.payload=payload
        self.conditions=conditions or {}
        self.collection=INVENTORY_COLLECTION
        self.base_Repo_obj=ReadDbBaseRepo(collection=self.collection)

    async def create(self):
        if not isinstance(self.payload, (InventoryReadModel, ProdInvReadModel)):
            return False

        data=self.payload.model_dump(mode="json",exclude_unset=True)
        return (await self.base_Repo_obj.create(data=data)).acknowledged
    
    async def update(self):
        if not self.payload:
            return False
        
        data=self.payload.model_dump(mode="json",exclude_unset=True) if hasattr(self.payload, 'model_dump') else self.payload
        return (await self.base_Repo_obj.update(data=data,conditions=self.conditions))
    
    async def delete(self):
        return (await self.base_Repo_obj.delete(conditions=self.conditions))
    
    async def get(self,query:str,limit:Optional[int]=None,offset:Optional[int]=None):
        query=query.strip()
        queries={
            "$or":[
                {'id':{'$regex':query,'$options':'i'}},
                {'ui_id':{'$regex':query,'$options':'i'}},
                {'shop_id':{'$regex':query,'$options':'i'}},
                {'sku':{'$regex':query,'$options':'i'}},
                {'barcode':{'$regex':query,'$options':'i'}},
                {'name':{'$regex':query,'$options':'i'}},
                {'category':{'$regex':query,'$options':'i'}},
                {'description':{'$regex':query,'$options':'i'}}
            ]
        }

        return await self.base_Repo_obj.get(queries=queries,offset=offset,limit=limit)
    
    async def getby_queries(self,queries:dict,limit:Optional[int]=None,offset:Optional[int]=None):
        return await self.base_Repo_obj.get(queries=queries,limit=limit,offset=offset)
    
    async def get_one(self,queries:dict):
        return await self.base_Repo_obj.get_one(queries=queries)
    
    async def update_stocks(self, product_id: str, physical_stocks: float, reserved_stocks: float):
        """
        Updates the stocks (physical, reserved, and available) for a specific product.
        """
        update_data = {
            "stocks": physical_stocks - reserved_stocks,
            "stock_infos.physical_stocks": physical_stocks,
            "stock_infos.reserved_stocks": reserved_stocks,
            "stock_infos.available_Stocks": physical_stocks - reserved_stocks,
        }
        
        self.conditions = {"id": product_id}
        self.payload = update_data
        return await self.update()

    async def update_stocks_bulk(self, data: list):
        """
        data: list of dicts containing:
        {'product_id': str, 'variant_id': str, 'batch_id': str, 'physical_stocks': float, 'reserved_stocks': float}
        """
        bulk_update_data = []
        for item in data:
            product_id = item.get('product_id')
            variant_id = item.get('variant_id')
            batch_id = item.get('batch_id')
            physical_stocks = item.get('physical_stocks', 0)
            reserved_stocks = item.get('reserved_stocks', 0)
            available_stocks = physical_stocks - reserved_stocks

            ic(physical_stocks,reserved_stocks,available_stocks)
            
            filter_query = {'id': product_id}
            
            if variant_id:
                # 1. Update ProdInvReadModel structure
                update_query_units = {
                    '$set': {
                        'inventory_units.$[unit].stock_infos.physical_stocks': physical_stocks,
                        'inventory_units.$[unit].stock_infos.reserved_stocks': reserved_stocks,
                        'inventory_units.$[unit].stock_infos.available_Stocks': available_stocks,
                        'stocks': available_stocks
                    }
                }
                array_filters_units = [{'unit.variant_infos.id': variant_id}]
                if batch_id:
                    array_filters_units[0]['unit.batch_infos.id'] = batch_id
                
                filter_query_units = {**filter_query, 'inventory_units': {'$type': 'array'}}
                bulk_update_data.append(UpdateOne(filter_query_units, update_query_units, array_filters=array_filters_units))

                # 2. Update InventoryReadModel structure
                update_query_vars = {
                    '$set': {
                        'variants.$[var].stocks': available_stocks,
                        'stocks': available_stocks
                    }
                }
                array_filters_vars = [{'var.id': variant_id}]
                filter_query_vars = {**filter_query, 'variants': {'$type': 'array'}}
                bulk_update_data.append(UpdateOne(filter_query_vars, update_query_vars, array_filters=array_filters_vars))

                if batch_id:
                    update_query_batches = {
                        '$set': {
                            'batches.$[batch].stocks': available_stocks,
                            'stocks': available_stocks
                        }
                    }
                    array_filters_batches = [{'batch.id': batch_id}]
                    filter_query_batches = {**filter_query, 'batches': {'$type': 'array'}}
                    bulk_update_data.append(UpdateOne(filter_query_batches, update_query_batches, array_filters=array_filters_batches))
            else:
                update_query = {
                    '$set': {
                        'stocks': available_stocks,
                        'inventory_units.0.stock_infos.physical_stocks': physical_stocks,
                        'inventory_units.0.stock_infos.reserved_stocks': reserved_stocks,
                        'inventory_units.0.stock_infos.available_Stocks': available_stocks
                    }
                }
                bulk_update_data.append(UpdateOne(filter_query, update_query))

        if not bulk_update_data:
            return False
            
        return await self.base_Repo_obj.update_bulk(ops=bulk_update_data)
