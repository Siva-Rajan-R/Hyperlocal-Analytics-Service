from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime


class SupplierAnalyticsDatas(BaseModel):
    supplier_id: str
    outstanding_amounts: Optional[float] = 0
    cleared_amounts: Optional[float] = 0


class SupplierAnalyticsSchema(BaseModel):
    shop_id: str
    datas: List[SupplierAnalyticsDatas]