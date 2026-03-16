import contextvars
import json
import logging
from datetime import datetime, timezone


correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar('correlation_id', default=None)
tenant_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar('tenant_id', default=None)
user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar('user_id', default=None)
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar('request_id', default=None)


def get_correlation_id() -> str | None:
    return correlation_id_var.get()


def get_tenant_id() -> str | None:
    return tenant_id_var.get()


def get_user_id() -> str | None:
    return user_id_var.get()


def get_request_id() -> str | None:
    return request_id_var.get()


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 - matches logging.Filter API
        record.correlation_id = get_correlation_id()
        record.tenant_id = get_tenant_id()
        record.user_id = get_user_id()
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', None),
            'tenant_id': getattr(record, 'tenant_id', None),
            'user_id': getattr(record, 'user_id', None),
            'request_id': getattr(record, 'request_id', None),
        }
        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
