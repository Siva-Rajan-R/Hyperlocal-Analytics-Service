from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime


class SupplierOverallAnalytics(BaseModel):
    shop_id:str
    total_suppliers:int
    total_outstandings:float



class SupplierBreakDownAnalytics(BaseModel):
    shop_id:str
    supplier_id:str
    total_purchases:int
    timestamp:datetime
