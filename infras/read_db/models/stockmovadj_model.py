from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime


class StockMovAdjOverallAnalytics(BaseModel):
    shop_id:str
    total_stockmovadj:int
    total_stockmovadj_increments:float
    total_stockmovadj_decrements:float
    total_stockmovadj_increments_count:Optional[int] = 0
    total_stockmovadj_decrements_count:Optional[int] = 0
