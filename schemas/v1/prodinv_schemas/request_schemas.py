from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime


class ProdInvAnalyticsDatas(BaseModel):
    product_id:str
    variant_id:Optional[str]=None
    batch_id:Optional[str]=None
    is_active:Optional[bool]=None
    have_tracking:Optional[bool]=True
    stocks:Optional[float]=0
    low_stocks:Optional[float]=0
    no_stocks:Optional[float]=0
    created_at:Optional[str]=None


class ProdInvAnalyticsSchema(BaseModel):
    shop_id:str
    datas:List[ProdInvAnalyticsDatas]