from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime


class PurchaseAnalyticsDatas(BaseModel):
    purchase_id:str
    supplier_id:str
    product_id:str
    variant_id:Optional[str]=None
    batch_id:Optional[str]=None
    stocks:Optional[float]=0
    purchase_amounts:Optional[float]=0
    outstanding_amounts:Optional[float]=0


class PurchaseAnalyticsSchema(BaseModel):
    shop_id:str
    total_purchase:Optional[int]=1
    datas:List[PurchaseAnalyticsDatas]
