import asyncio
from icecream import ic
from typing import Optional, List
import urllib.request
import json

async def emit_notification(
    title: str,
    message: str,
    type: str = "info",  # info, error, warning, success, announcement
    user_id: Optional[str] = None,
    user_ids: Optional[List[str]] = None,
    target_type: str = "particular",  # all, particular
    additional_metadata: Optional[dict] = None
):
    payload = {
        "title": title,
        "message": message,
        "type": type,
        "user_id": user_id,
        "user_ids": user_ids,
        "target_type": target_type,
        "additional_metadata": additional_metadata or {}
    }

    # 1. Try RabbitMQ event publish
    published_mq = False
    try:
        from messaging.main import RabbitMQMessagingConfig, ExchangeType
        rabbitmq_conn = await RabbitMQMessagingConfig.get_rabbitmq_connection()
        rabbitmq_msg_obj = RabbitMQMessagingConfig(rabbitMQ_connection=rabbitmq_conn)
        
        # Ensure exchange exists
        exchange_name = 'notifications.service.exchange'
        await rabbitmq_msg_obj.create_exchange(name=exchange_name, exchange_type=ExchangeType.DIRECT)
        
        await rabbitmq_msg_obj.publish_event(
            routing_key="notifications.service.routing.key",
            exchange_name=exchange_name,
            payload=payload,
            headers={}
        )
        published_mq = True
        ic(f"Notification event emitted via RabbitMQ successfully: {title}")
    except Exception as e:
        ic(f"RabbitMQ notification emit failed: {e}")

    # 2. Direct HTTP fallback to Notification Service on port 8009 if MQ wasn't sent
    if not published_mq:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8009/notifications/send",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                ic(f"Notification emitted directly via HTTP fallback: {resp.status}")
        except Exception as http_err:
            ic(f"Failed to emit notification via HTTP fallback: {http_err}")
