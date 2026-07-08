from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime


class StockMovAdjAnalyticsDatas(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    batch_id: Optional[str] = None
    stocks: Optional[float] = 0
    type: Optional[str] = None


class StockMovAdjAnalyticsSchema(BaseModel):
    shop_id: str
    datas: List[StockMovAdjAnalyticsDatas]