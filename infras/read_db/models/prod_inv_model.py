from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime


class ProdInvOverallAnalytics(BaseModel):
    shop_id:str
    total_active_products:int
    total_inactive_product:int
    total_stocks:float
    total_low_stocks:float
    total_no_stocks:float


class ProdInvBreakDownAnalytics(BaseModel):
    shop_id:str
    product_id:str
    variant_id:str
    batch_id:str
    total_purchases:int
    total_purchase_amounts:float
    total_purchase_outstanding_amounts:float
    total_offline_sales:int
    total_offline_sales_amount:float
    total_online_sales:int
    total_online_sales_amount:float
    total_stockmovadj_increments:float
    total_stockmovadj_decrements:float

    timestamp:datetime