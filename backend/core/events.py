import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import pika

logger = logging.getLogger(__name__)


def build_event_payload(
    *,
    event_type: str,
    tenant_id: str,
    correlation_id: str | None = None,
    user_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        'event_type': event_type,
        'tenant_id': tenant_id,
        'correlation_id': correlation_id or str(uuid.uuid4()),
        'user_id': user_id,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'data': data or {},
    }


def publish_event(
    *,
    exchange: str,
    routing_key: str,
    payload: dict[str, Any],
    rabbitmq_url: str | None = None,
) -> None:
    rabbitmq_url = rabbitmq_url or os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
    params = pika.URLParameters(rabbitmq_url)
    connection = pika.BlockingConnection(params)
    try:
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)
        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(payload).encode('utf-8'),
            properties=pika.BasicProperties(content_type='application/json', delivery_mode=2),
        )
    finally:
        connection.close()


def maybe_publish_event(
    *,
    event_type: str,
    tenant_id: str,
    routing_key: str,
    correlation_id: str | None = None,
    user_id: str | None = None,
    data: dict[str, Any] | None = None,
    exchange: str | None = None,
    rabbitmq_url: str | None = None,
) -> None:
    rabbitmq_url = rabbitmq_url or os.environ.get('RABBITMQ_URL')
    if not rabbitmq_url:
        return
    exchange = exchange or os.environ.get('EDMP_EVENT_EXCHANGE', 'edmp.events')

    payload = build_event_payload(
        event_type=event_type,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        user_id=user_id,
        data=data,
    )
    try:
        publish_event(exchange=exchange, routing_key=routing_key, payload=payload, rabbitmq_url=rabbitmq_url)
    except Exception:
        logger.exception('Failed to publish event %s to %s', event_type, routing_key)
        return
