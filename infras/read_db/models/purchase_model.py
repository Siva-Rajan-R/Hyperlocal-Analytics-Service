from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime


class PurchaseOverallAnalytics(BaseModel):
    shop_id:str
    total_purchase:float
    total_purchase_amounts:float
    total_purchase_stocks:float
    total_outstanding_amounts:float

