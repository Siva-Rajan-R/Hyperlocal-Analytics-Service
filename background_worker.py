import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from arq.connections import RedisSettings
import redis.asyncio as aioredis
from infras.read_db.repos.sync_service import SyncService

REDIS_URL = os.getenv("PLATFORM_REDIS_URL") or "redis://localhost:6379"
redis_settings = RedisSettings.from_dsn(REDIS_URL)

async def sync_analytics_task(ctx, payload: dict):
    shop_id = payload.get("shop_id")
    job_id = payload.get("job_id")
    redis_client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)

    # 1. Update status to IN_PROGRESS
    if job_id:
        job_data = {
            "job_id": job_id,
            "shop_id": shop_id,
            "status": "IN_PROGRESS",
            "started_at": datetime.now(timezone.utc).isoformat()
        }
        await redis_client.set(f"SYNC_JOB:{job_id}", json.dumps(job_data), ex=86400)
        if shop_id:
            await redis_client.set(f"SYNC_JOB:SHOP:{shop_id}", json.dumps(job_data), ex=86400)

    user_id = payload.get("user_id")

    try:
        from helpers.emit_notification import emit_notification
    except ImportError:
        emit_notification = None

    try:
        res = await SyncService.sync_shop_data(shop_id=shop_id)

        # 2. Update status to COMPLETED
        if job_id:
            job_data = {
                "job_id": job_id,
                "shop_id": shop_id,
                "status": "COMPLETED",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": res
            }
            await redis_client.set(f"SYNC_JOB:{job_id}", json.dumps(job_data), ex=86400)
            if shop_id:
                await redis_client.set(f"SYNC_JOB:SHOP:{shop_id}", json.dumps(job_data), ex=86400)

        # 3. Emit real-time notification to user/shop
        if emit_notification:
            try:
                await emit_notification(
                    title="Analytics Sync Finished",
                    message="Shop analytics data has been synchronized successfully.",
                    type="success",
                    user_id=user_id,
                    target_type="particular" if user_id else "all",
                    additional_metadata={
                        "type": "analytics_sync",
                        "shop_id": shop_id,
                        "status": "COMPLETED",
                        "job_id": job_id
                    }
                )
            except Exception as notif_err:
                print(f"[Sync Worker] Notification emission warning: {notif_err}")

        return res
    except Exception as e:
        if job_id:
            job_data = {
                "job_id": job_id,
                "shop_id": shop_id,
                "status": "FAILED",
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
            await redis_client.set(f"SYNC_JOB:{job_id}", json.dumps(job_data), ex=86400)
            if shop_id:
                await redis_client.set(f"SYNC_JOB:SHOP:{shop_id}", json.dumps(job_data), ex=86400)

        if emit_notification:
            try:
                await emit_notification(
                    title="Analytics Sync Failed",
                    message=f"Failed to synchronize analytics: {str(e)}",
                    type="error",
                    user_id=user_id,
                    target_type="particular" if user_id else "all",
                    additional_metadata={
                        "type": "analytics_sync",
                        "shop_id": shop_id,
                        "status": "FAILED",
                        "job_id": job_id
                    }
                )
            except Exception:
                pass

        raise e
    finally:
        await redis_client.aclose()


async def startup(ctx):
    pass

async def shutdown(ctx):
    pass

class WorkerSettings:
    queue_name = "analytics_sync_queue"
    redis_settings = redis_settings
    functions = [sync_analytics_task]
    on_startup = startup
    on_shutdown = shutdown
