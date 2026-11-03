from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class SalesAnalyticsDatas(BaseModel):
    sales_id: str
    customer_id: Optional[str] = None
    product_id: str
    variant_id: Optional[str] = None
    batch_id: Optional[str] = None
    stocks: Optional[float] = 0        # Quantity sold
    sales_amounts: Optional[float] = 0 # Amount of sale
    cost_amounts: Optional[float] = 0  # Cost of goods sold
    profit_amounts: Optional[float] = 0 # Profit from sale
    sales_type: str                   # "ONLINE" or "OFFLINE"
    payment_method: Optional[str] = None
    payments: Optional[Dict[str, float]] = None
    bill_amount: Optional[float] = 0.0
    received_amount: Optional[float] = 0.0
    created_at: Optional[str] = None

    model_config = ConfigDict(extra='allow')


class SalesAnalyticsSchema(BaseModel):
    shop_id: str
    datas: List[SalesAnalyticsDatas]
