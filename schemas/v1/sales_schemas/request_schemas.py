from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class SalesAnalyticsDatas(BaseModel):
    sales_id: str
    customer_id: Optional[str] = None
    product_id: str
    variant_id: Optional[str] = None
    batch_id: Optional[str] = None
    stocks: Optional[float] = 0        # Quantity sold
    sales_amounts: Optional[float] = 0 # Amount of sale
    sales_type: str                   # "ONLINE" or "OFFLINE"


class SalesAnalyticsSchema(BaseModel):
    shop_id: str
    datas: List[SalesAnalyticsDatas]
