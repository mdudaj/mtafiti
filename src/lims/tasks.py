from __future__ import annotations

from celery import shared_task

from core.celery import TenantTask

from .models import TanzaniaAddressSyncRun
from .services import process_tanzania_address_sync_run, sync_run_to_dict


@shared_task(base=TenantTask)
def sync_tanzania_address_run(*, tenant_schema: str, run_id: str) -> dict[str, object]:
    run = TanzaniaAddressSyncRun.objects.get(id=run_id)
    return process_tanzania_address_sync_run(run)


@shared_task(base=TenantTask)
def schedule_tanzania_address_sync(*, tenant_schema: str) -> dict[str, object]:
    run = (
        TanzaniaAddressSyncRun.objects.filter(
            status__in=[
                TanzaniaAddressSyncRun.Status.PENDING,
                TanzaniaAddressSyncRun.Status.PAUSED,
                TanzaniaAddressSyncRun.Status.RUNNING,
            ]
        )
        .order_by("-created_at")
        .first()
    )
    if run is None:
        run = TanzaniaAddressSyncRun.objects.create()
    if run.status == TanzaniaAddressSyncRun.Status.RUNNING:
        return sync_run_to_dict(run)
    return process_tanzania_address_sync_run(run)
