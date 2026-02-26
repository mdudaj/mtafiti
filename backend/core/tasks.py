from celery import shared_task

from .celery import TenantTask
from .logging import get_correlation_id, get_request_id, get_tenant_id, get_user_id


@shared_task(base=TenantTask)
def ping(*, tenant_schema: str) -> str:
    return f'pong:{tenant_schema}'


@shared_task(base=TenantTask)
def context_ping(*, tenant_schema: str) -> dict[str, str | None]:
    return {
        'tenant_id': get_tenant_id(),
        'correlation_id': get_correlation_id(),
        'user_id': get_user_id(),
        'request_id': get_request_id(),
    }
