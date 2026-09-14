import os
import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query, Header, HTTPException, status
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

    job_data = {
        "job_id": job_id,
        "shop_id": shop_id,
        "user_id": target_user_id,
        "status": "QUEUED",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    # 1. Record initial QUEUED status in Redis
    try:
        redis_client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.set(f"SYNC_JOB:{job_id}", json.dumps(job_data), ex=86400)
        await redis_client.set(f"SYNC_JOB:SHOP:{shop_id}", json.dumps(job_data), ex=86400)
        await redis_client.aclose()
    except Exception as redis_err:
        print(f"[Sync API] Warning: Failed to set initial Redis status: {redis_err}")

    # 2. Enqueue in ARQ background worker queue
    enqueued = False
    try:
        arq_pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        await arq_pool.enqueue_job("sync_analytics_task", payload, _queue_name="analytics_sync_queue")
        await arq_pool.aclose()
        enqueued = True
        print(f"[Sync API] Enqueued ARQ task for shop {shop_id}, job {job_id}")
    except Exception as arq_err:
        print(f"[Sync API] ARQ pool enqueue failed, falling back to background asyncio task: {arq_err}")
        try:
            from background_worker import sync_analytics_task
            asyncio.create_task(sync_analytics_task(None, payload))
            enqueued = True
        except Exception as bg_err:
            print(f"[Sync API] Background task creation failed: {bg_err}")

    return {
        "success": True,
        "msg": "Analytics synchronization scheduled in background",
        "job_id": job_id,
        "status": "QUEUED",
        "data": job_data
    }


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
