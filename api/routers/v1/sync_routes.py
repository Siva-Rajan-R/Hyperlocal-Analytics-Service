import os
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query, Header, HTTPException
from arq import create_pool
from arq.connections import RedisSettings
import redis.asyncio as aioredis
from infras.read_db.repos.sync_service import SyncService
from helpers.emit_notification import emit_notification

router = APIRouter(
    prefix="/analytics-dashboard/sync",
    tags=["Analytics Sync"],
)

REDIS_URL = os.getenv("PLATFORM_REDIS_URL") or "redis://localhost:6379"

@router.post("")
async def sync_shop_data(
    shop_id: str = Query(...),
    user_id: Optional[str] = Query(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id")
):
    target_user_id = user_id or x_user_id
    job_id = str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "shop_id": shop_id,
        "user_id": target_user_id
    }

    try:
        # 1. Enqueue background task via ARQ
        redis_pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        await redis_pool.enqueue_job(
            "sync_analytics_task",
            payload,
            _job_id=job_id,
            _queue_name="analytics_sync_queue"
        )
        await redis_pool.close()

        # 2. Store initial status in Redis
        redis_client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)
        job_data = {
            "job_id": job_id,
            "shop_id": shop_id,
            "user_id": target_user_id,
            "status": "QUEUED",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await redis_client.set(f"SYNC_JOB:{job_id}", json.dumps(job_data), ex=86400)
        await redis_client.set(f"SYNC_JOB:SHOP:{shop_id}", json.dumps(job_data), ex=86400)
        await redis_client.aclose()

        return {
            "success": True,
            "msg": "Analytics synchronization scheduled in background",
            "job_id": job_id,
            "status": "QUEUED",
            "data": job_data
        }
    except Exception as e:
        # Fallback to direct synchronous execution if ARQ/Redis enqueue fails
        try:
            res = await SyncService.sync_shop_data(shop_id=shop_id)
            try:
                await emit_notification(
                    title="Analytics Sync Finished",
                    message="Shop analytics data has been synchronized successfully.",
                    type="success",
                    user_id=target_user_id,
                    target_type="particular" if target_user_id else "all",
                    additional_metadata={
                        "type": "analytics_sync",
                        "shop_id": shop_id,
                        "status": "COMPLETED",
                        "job_id": job_id
                    }
                )
            except Exception:
                pass

            return {
                "success": True,
                "msg": "Analytics synchronization completed",
                "job_id": job_id,
                "status": "COMPLETED",
                "data": res
            }
        except Exception as sync_err:
            try:
                await emit_notification(
                    title="Analytics Sync Failed",
                    message=f"Failed to synchronize analytics: {str(sync_err)}",
                    type="error",
                    user_id=target_user_id,
                    target_type="particular" if target_user_id else "all",
                    additional_metadata={
                        "type": "analytics_sync",
                        "shop_id": shop_id,
                        "status": "FAILED",
                        "job_id": job_id
                    }
                )
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"Sync failed: {str(sync_err)}")


@router.get("/status/{job_id}")
async def get_sync_job_status(job_id: str):
    redis_client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        raw = await redis_client.get(f"SYNC_JOB:{job_id}")
        if not raw:
            raise HTTPException(status_code=404, detail="Sync job not found")
        return {
            "success": True,
            "data": json.loads(raw)
        }
    finally:
        await redis_client.aclose()

@router.get("/status-by-shop/{shop_id}")
async def get_sync_status_by_shop(shop_id: str):
    redis_client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        raw = await redis_client.get(f"SYNC_JOB:SHOP:{shop_id}")
        if not raw:
            return {
                "success": True,
                "data": None
            }
        return {
            "success": True,
            "data": json.loads(raw)
        }
    finally:
        await redis_client.aclose()
