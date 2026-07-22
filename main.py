from fastapi import FastAPI
from api.routers.v1 import supplier_routes,prod_inv_routes,purchase_routes,stockmovadj_routes,customer_routes,sales_routes
from contextlib import asynccontextmanager
from icecream import ic
from dotenv import load_dotenv
from core.configs.settings_config import SETTINGS
from hyperlocal_platform.core.enums.environment_enum import EnvironmentEnum
import os,asyncio
from hyperlocal_platform.infras.saga.main import init_infra_db
from messaging.worker import worker
from infras.caching.main import redis_client,check_redis_health
load_dotenv()


@asynccontextmanager
async def analytics_service_lifespan(app:FastAPI):
    try:
        ic("Starting analytics service...")
        await init_infra_db()
        await check_redis_health()
        # await redis_client.flushdb()
        asyncio.create_task(worker())
        yield

    except Exception as e:
        ic(f"Error : Starting analytics service => {e}")

    finally:
        ic("...Stoping analytics Servcie...")

debug=False
openapi_url=None
docs_url=None
redoc_url=None

if SETTINGS.ENVIRONMENT.value==EnvironmentEnum.DEVELOPMENT.value:
    debug=True
    openapi_url="/openapi.json"
    docs_url="/docs"
    redoc_url="/redoc"

app=FastAPI(
    title="Analytics Service",
    description="This service contains all the CRUD operations for analytics service",
    debug=debug,
    openapi_url=openapi_url,
    docs_url=docs_url,
    redoc_url=redoc_url,
    lifespan=analytics_service_lifespan,
    root_path="/analytics"

)



from api.routers.v1 import supplier_routes,prod_inv_routes,purchase_routes,stockmovadj_routes,customer_routes,sales_routes,analytics_routes,sync_routes

# Routes to include
app.include_router(prod_inv_routes.router)
app.include_router(customer_routes.router)
app.include_router(supplier_routes.router)
app.include_router(stockmovadj_routes.router)
app.include_router(purchase_routes.router)
app.include_router(sales_routes.router)
app.include_router(analytics_routes.router)
app.include_router(sync_routes.router)

