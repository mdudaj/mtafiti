from celery import shared_task

from .celery import TenantTask


@shared_task(base=TenantTask)
def ping(*, tenant_schema: str) -> str:
    return f'pong:{tenant_schema}'

