from __future__ import annotations

from math import ceil

from celery import shared_task
from django.utils import timezone

from core.celery import TenantTask

from .models import TanzaniaAddressSyncRun
from .services import process_tanzania_address_sync_run, sync_run_to_dict


def _schedule_sync_resume(*, tenant_schema: str, run: TanzaniaAddressSyncRun) -> None:
    queue = (run.checkpoint or {}).get("queue") or []
    if not queue:
        return
    if run.status != TanzaniaAddressSyncRun.Status.PAUSED:
        return
    countdown = 1
    if run.next_not_before_at:
        countdown = max(1, ceil((run.next_not_before_at - timezone.now()).total_seconds()))
    sync_tanzania_address_run.apply_async(
        kwargs={
            "tenant_schema": tenant_schema,
            "run_id": str(run.id),
        },
        countdown=countdown,
    )


@shared_task(base=TenantTask)
def sync_tanzania_address_run(*, tenant_schema: str, run_id: str) -> dict[str, object]:
    run = TanzaniaAddressSyncRun.objects.get(id=run_id)
    result = process_tanzania_address_sync_run(run)
    run.refresh_from_db()
    _schedule_sync_resume(tenant_schema=tenant_schema, run=run)
    return result


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
    result = process_tanzania_address_sync_run(run)
    run.refresh_from_db()
    _schedule_sync_resume(tenant_schema=tenant_schema, run=run)
    return result
