from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime


class CustomerAnalyticsDatas(BaseModel):
    customer_id: str
    credit_limit: Optional[float] = 0
    outstanding_amounts: Optional[float] = 0
    cleared_amounts: Optional[float] = 0


class CustomerAnalyticsSchema(BaseModel):
    shop_id: str
    action: Optional[str] = "create"
    datas: List[CustomerAnalyticsDatas]