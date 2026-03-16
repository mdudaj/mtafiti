import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import pika

from .logging import get_correlation_id, get_request_id, get_user_id

logger = logging.getLogger(__name__)


_REQUIRED_ENVELOPE_FIELDS = {
    'event_type': str,
    'tenant_id': str,
    'correlation_id': str,
    'timestamp': str,
    'data': dict,
}

_REQUIRED_DOMAIN_DATA_FIELDS = {
    'workflow.definition.': {'id', 'name'},
    'workflow.run.': {'id', 'definition_id', 'status'},
    'orchestration.workflow.': {'id', 'name', 'trigger_type', 'status'},
    'orchestration.run.': {'id', 'workflow_id', 'status', 'step_results'},
    'stewardship.item.': {'id', 'item_type', 'subject_ref', 'severity', 'status'},
    'agent.run.': {'id', 'prompt', 'allowed_tools', 'timeout_seconds', 'status'},
}

_REQUIRED_AUDIT_DATA_FIELDS = {'action', 'resource_type', 'resource_id', 'details'}


def validate_event_payload(payload: dict[str, Any]) -> None:
    for field_name, field_type in _REQUIRED_ENVELOPE_FIELDS.items():
        value = payload.get(field_name)
        if not isinstance(value, field_type):
            raise ValueError(f'invalid_event_payload:{field_name}')
        if field_type is str and not value:
            raise ValueError(f'invalid_event_payload:{field_name}')

    event_type = payload['event_type']
    data = payload['data']

    if event_type.startswith('audit.'):
        missing = sorted(_REQUIRED_AUDIT_DATA_FIELDS - set(data.keys()))
        if missing:
            raise ValueError(f'invalid_audit_payload:missing={",".join(missing)}')
        if not isinstance(data.get('details'), dict):
            raise ValueError('invalid_audit_payload:details')
        return

    for event_prefix, required_fields in _REQUIRED_DOMAIN_DATA_FIELDS.items():
        if event_type.startswith(event_prefix):
            missing = sorted(required_fields - set(data.keys()))
            if missing:
                raise ValueError(
                    f'invalid_domain_payload:{event_prefix}missing={",".join(missing)}'
                )
            return


def build_event_payload(
    *,
    event_type: str,
    tenant_id: str,
    correlation_id: str | None = None,
    user_id: str | None = None,
    request_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        'event_type': event_type,
        'tenant_id': tenant_id,
        'correlation_id': correlation_id or get_correlation_id() or str(uuid.uuid4()),
        'user_id': user_id if user_id is not None else get_user_id(),
        'request_id': request_id if request_id is not None else get_request_id(),
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
    request_id: str | None = None,
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
        request_id=request_id,
        data=data,
    )
    validate_event_payload(payload)
    try:
        publish_event(exchange=exchange, routing_key=routing_key, payload=payload, rabbitmq_url=rabbitmq_url)
    except Exception:
        logger.exception('Failed to publish event %s to %s', event_type, routing_key)
        return


def maybe_publish_audit_event(
    *,
    tenant_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    correlation_id: str | None = None,
    user_id: str | None = None,
    request_id: str | None = None,
    data: dict[str, Any] | None = None,
    exchange: str | None = None,
    rabbitmq_url: str | None = None,
) -> None:
    maybe_publish_event(
        event_type=f'audit.{action}',
        tenant_id=tenant_id,
        routing_key=f'{tenant_id}.audit.{action}',
        correlation_id=correlation_id,
        user_id=user_id,
        request_id=request_id,
        data={
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'details': data or {},
        },
        exchange=exchange,
        rabbitmq_url=rabbitmq_url,
    )
