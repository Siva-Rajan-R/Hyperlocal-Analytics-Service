from motor.motor_asyncio import AsyncIOMotorClient
from core.configs.settings_config import SETTINGS
import asyncio
from icecream import ic


READ_DB_URL=SETTINGS.READ_DB_URL

CLIENT=AsyncIOMotorClient(READ_DB_URL)
READ_DATABASE=CLIENT['AnalyticsDb']
PROCESSED_EVENTS = READ_DATABASE["ProcessedEvents"]


ANALYTICS_COLLECTIONS = {
    "supplier": {
        "overall": READ_DATABASE["SupplierOverallAnalytics"],
        "breakdown": READ_DATABASE["SupplierBreakdownAnalytics"],
    },

    "customer": {
        "overall": READ_DATABASE["CustomerOverallAnalytics"],
        "breakdown": READ_DATABASE["CustomerBreakdownAnalytics"],
    },

    "purchase": {
        "overall": READ_DATABASE["PurchaseOverallAnalytics"],
        "daily": READ_DATABASE["PurchaseDailyAnalytics"],
    },

    "prodinv": {
        "overall": READ_DATABASE["ProdInvOverallAnalytics"],
        "breakdown": READ_DATABASE["ProdInvBreakdownAnalytics"],
    },

    "stockmovadj": {
        "overall": READ_DATABASE["StockMovAdjOverallAnalytics"],
        "daily": READ_DATABASE["StockMovAdjDailyAnalytics"],
    },

    "sales": {
        "overall": READ_DATABASE["SalesOverallAnalytics"],
        "daily": READ_DATABASE["SalesDailyAnalytics"],
    },
}

