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
    sales_amounts: Optional[float] = 0 # Net realized revenue with GST
    cost_amounts: Optional[float] = 0  # Cost of goods sold (with GST)
    profit_amounts: Optional[float] = 0 # Net realized profit
    sales_type: str                   # "ONLINE" or "OFFLINE"
    payment_method: Optional[str] = None
    payments: Optional[Dict[str, float]] = None
    bill_amount: Optional[float] = 0.0
    received_amount: Optional[float] = 0.0
    gross_revenue: Optional[float] = 0.0
    refund_amount: Optional[float] = 0.0
    taxable_revenue: Optional[float] = 0.0
    cost_with_gst: Optional[float] = 0.0
    base_cost: Optional[float] = 0.0
    returned_cost: Optional[float] = 0.0
    sales_gst_amount: Optional[float] = 0.0
    returned_gst: Optional[float] = 0.0
    itc_amount: Optional[float] = 0.0
    transport_charges: Optional[float] = 0.0
    is_gst_reg: Optional[bool] = False
    created_at: Optional[str] = None

    model_config = ConfigDict(extra='allow')


class SalesAnalyticsSchema(BaseModel):
    shop_id: str
    datas: List[SalesAnalyticsDatas]
