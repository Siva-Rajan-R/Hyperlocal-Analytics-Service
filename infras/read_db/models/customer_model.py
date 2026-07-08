from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime


class CustomerOverallAnalytics(BaseModel):
    shop_id:str
    total_customers:int
    total_credit_limits:float
    total_outstandings:float
    total_settlements:float


class CustomerBreakDownAnalytics(BaseModel):
    shop_id:str
    customer_id:str
    total_customers:int
    total_outstandings:float
    total_settlements:float
    total_sales:int
    total_sales_amount:float

    timestamp:datetime
