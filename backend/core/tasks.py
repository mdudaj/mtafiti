import re
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .celery import TenantTask
from .events import maybe_publish_audit_event, maybe_publish_event
from .logging import get_correlation_id, get_request_id, get_tenant_id, get_user_id
from .models import (
    Classification,
    ConnectorRun,
    DataAsset,
    IngestionRequest,
    QualityCheckResult,
    QualityRule,
    RetentionHold,
    RetentionRun,
)

CLASSIFICATION_SENSITIVITY = {
    Classification.Level.PUBLIC: 0,
    Classification.Level.INTERNAL: 1,
    Classification.Level.CONFIDENTIAL: 2,
    Classification.Level.RESTRICTED: 3,
}


def _classification_max_sensitivity(values: list[str]) -> int:
    return max((CLASSIFICATION_SENSITIVITY.get(item, -1) for item in values), default=-1)


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


@shared_task(base=TenantTask)
def evaluate_quality_rule(*, tenant_schema: str, rule_id: str) -> dict[str, str]:
    rule = QualityRule.objects.select_related('asset').get(id=rule_id)
    forced = (rule.params or {}).get('force_status')
    status = forced if forced in {'pass', 'warn', 'fail', 'error'} else 'pass'

    if rule.rule_type == 'freshness' and forced is None:
        max_age_minutes = (rule.params or {}).get('max_age_minutes')
        if isinstance(max_age_minutes, int) and max_age_minutes >= 0:
            age_minutes = (timezone.now() - rule.asset.updated_at).total_seconds() / 60.0
            if age_minutes > max_age_minutes:
                status = 'warn' if rule.severity == QualityRule.Severity.WARNING else 'fail'

    result = QualityCheckResult.objects.create(
        rule=rule,
        status=status,
        details={'rule_type': rule.rule_type, 'severity': rule.severity},
    )
    correlation_id = get_correlation_id()
    user_id = get_user_id()
    request_id = get_request_id()
    event_type = 'quality.check.failed' if status in {'fail', 'error'} else 'quality.check.completed'
    maybe_publish_event(
        event_type=event_type,
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.{event_type}',
        correlation_id=correlation_id,
        user_id=user_id,
        request_id=request_id,
        data={'rule_id': str(rule.id), 'result_id': str(result.id), 'status': status, 'asset_id': str(rule.asset_id)},
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='quality.rule.evaluated',
        resource_type='quality_rule',
        resource_id=str(rule.id),
        correlation_id=correlation_id,
        user_id=user_id,
        request_id=request_id,
        data={'result_id': str(result.id), 'status': status, 'asset_id': str(rule.asset_id)},
    )
    return {'rule_id': str(rule.id), 'result_id': str(result.id), 'status': status}


def _parse_period_days(period: str) -> int:
    m = re.fullmatch(r'P(\d+)D', period or '')
    if not m:
        raise ValueError('retention_period/grace_period must use ISO day format PnD')
    return int(m.group(1))


@shared_task(base=TenantTask)
def execute_retention_run(*, tenant_schema: str, run_id: str) -> dict[str, int | str]:
    run = RetentionRun.objects.select_related('rule').get(id=run_id)
    rule = run.rule
    now = timezone.now()
    retention_days = _parse_period_days(rule.retention_period)
    grace_days = _parse_period_days(rule.grace_period) if rule.grace_period else 0
    cutoff = now - timedelta(days=retention_days + grace_days)

    qs = DataAsset.objects.filter(created_at__lt=cutoff)
    scope = rule.scope or {}
    if scope.get('asset_types'):
        qs = qs.filter(asset_type__in=scope['asset_types'])
    if scope.get('owner'):
        qs = qs.filter(owner__iexact=scope['owner'])
    for tag in scope.get('tags', []) or []:
        qs = qs.filter(tags__contains=[tag])
    for classification in scope.get('classifications', []) or []:
        qs = qs.filter(classifications__contains=[classification])

    held_asset_ids = set(RetentionHold.objects.filter(active=True).values_list('asset_id', flat=True))
    candidates = [asset for asset in qs if asset.id not in held_asset_ids]
    correlation_id = get_correlation_id()
    user_id = get_user_id()
    request_id = get_request_id()
    maybe_publish_event(
        event_type='retention.run.started',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.retention.run.started',
        correlation_id=correlation_id,
        user_id=user_id,
        request_id=request_id,
        data={'run_id': str(run.id), 'rule_id': str(rule.id), 'mode': run.mode, 'candidate_count': len(candidates)},
    )

    archived_count = 0
    deleted_count = 0
    if run.mode == RetentionRun.Mode.EXECUTE:
        for asset in candidates:
            if rule.action == 'archive':
                props = dict(asset.properties)
                props['retention_state'] = 'archived'
                asset.properties = props
                asset.save(update_fields=['properties', 'updated_at'])
                archived_count += 1
                maybe_publish_event(
                    event_type='retention.asset.archived',
                    tenant_id=tenant_schema,
                    routing_key=f'{tenant_schema}.retention.asset.archived',
                    correlation_id=correlation_id,
                    user_id=user_id,
                    request_id=request_id,
                    data={'run_id': str(run.id), 'rule_id': str(rule.id), 'asset_id': str(asset.id)},
                )
            else:
                asset_id = str(asset.id)
                asset.delete()
                deleted_count += 1
                maybe_publish_event(
                    event_type='retention.asset.deleted',
                    tenant_id=tenant_schema,
                    routing_key=f'{tenant_schema}.retention.asset.deleted',
                    correlation_id=correlation_id,
                    user_id=user_id,
                    request_id=request_id,
                    data={'run_id': str(run.id), 'rule_id': str(rule.id), 'asset_id': asset_id},
                )

    summary = {
        'candidate_count': len(candidates),
        'archived_count': archived_count,
        'deleted_count': deleted_count,
        'held_count': len(held_asset_ids),
    }
    run.summary = summary
    run.status = RetentionRun.Status.COMPLETED
    run.completed_at = now
    run.save(update_fields=['summary', 'status', 'completed_at'])
    maybe_publish_event(
        event_type='retention.run.completed',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.retention.run.completed',
        correlation_id=correlation_id,
        user_id=user_id,
        request_id=request_id,
        data={'run_id': str(run.id), 'rule_id': str(rule.id), **summary},
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='retention.run.completed',
        resource_type='retention_run',
        resource_id=str(run.id),
        correlation_id=correlation_id,
        user_id=user_id,
        request_id=request_id,
        data={'rule_id': str(rule.id), **summary},
    )
    return {'run_id': str(run.id), **summary}


@shared_task(base=TenantTask)
def execute_connector_run(*, tenant_schema: str, run_id: str) -> dict[str, str | int]:
    run = ConnectorRun.objects.select_related("ingestion").get(id=run_id)
    ingestion = run.ingestion
    correlation_id = get_correlation_id()
    user_id = get_user_id()
    request_id = get_request_id()

    if run.status == ConnectorRun.Status.CANCELLED:
        return {"run_id": str(run.id), "status": run.status}

    run.status = ConnectorRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at", "updated_at"])
    ingestion.status = IngestionRequest.Status.RUNNING
    ingestion.save(update_fields=["status", "updated_at"])

    maybe_publish_event(
        event_type="connector.run.started",
        tenant_id=tenant_schema,
        routing_key=f"{tenant_schema}.connector.run.started",
        correlation_id=correlation_id,
        user_id=user_id,
        request_id=request_id,
        data={"run_id": str(run.id), "ingestion_id": str(ingestion.id)},
    )

    source = ingestion.source or {}
    force_status = source.get("force_status")
    processed_entities = int(source.get("processed_entities", 0) or 0)
    failed_entities = int(source.get("failed_entities", 0) or 0)
    incoming_classifications = source.get("classifications") or []
    existing_classifications = source.get("existing_classifications") or []
    actor_roles = set(source.get("actor_roles") or [])
    invalid_classifications = sorted(
        {
            value
            for value in incoming_classifications
            if value not in CLASSIFICATION_SENSITIVITY
        }
    )

    if invalid_classifications:
        run.status = ConnectorRun.Status.FAILED
        run.error_message = "unknown classifications: " + ", ".join(
            invalid_classifications
        )
        ingestion.status = IngestionRequest.Status.FAILED
    elif (
        _classification_max_sensitivity(incoming_classifications)
        > _classification_max_sensitivity(existing_classifications)
        and not actor_roles.intersection({"policy.admin", "tenant.admin"})
    ):
        run.status = ConnectorRun.Status.FAILED
        run.error_message = "classification sensitivity upgrade requires policy.admin"
        ingestion.status = IngestionRequest.Status.FAILED
    elif force_status == "failed":
        run.status = ConnectorRun.Status.FAILED
        run.error_message = str(source.get("error_message") or "connector execution failed")
        ingestion.status = IngestionRequest.Status.FAILED
    elif force_status == "cancelled":
        run.status = ConnectorRun.Status.CANCELLED
        run.error_message = str(source.get("error_message") or "connector execution cancelled")
        ingestion.status = IngestionRequest.Status.FAILED
    else:
        run.status = ConnectorRun.Status.SUCCEEDED
        ingestion.status = IngestionRequest.Status.COMPLETED

    run.progress = {
        "processed_entities": processed_entities,
        "failed_entities": failed_entities,
    }
    run.finished_at = timezone.now()
    run.save(
        update_fields=[
            "status",
            "error_message",
            "progress",
            "finished_at",
            "updated_at",
        ]
    )
    ingestion.save(update_fields=["status", "updated_at"])

    final_event_type = f"connector.run.{run.status}"
    maybe_publish_event(
        event_type=final_event_type,
        tenant_id=tenant_schema,
        routing_key=f"{tenant_schema}.{final_event_type}",
        correlation_id=correlation_id,
        user_id=user_id,
        request_id=request_id,
        data={
            "run_id": str(run.id),
            "ingestion_id": str(ingestion.id),
            "status": run.status,
            "progress": run.progress,
        },
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=final_event_type,
        resource_type="connector_run",
        resource_id=str(run.id),
        correlation_id=correlation_id,
        user_id=user_id,
        request_id=request_id,
        data={
            "ingestion_id": str(ingestion.id),
            "status": run.status,
            "progress": run.progress,
            "error_message": run.error_message,
        },
    )
    return {
        "run_id": str(run.id),
        "ingestion_id": str(ingestion.id),
        "status": run.status,
        "processed_entities": processed_entities,
        "failed_entities": failed_entities,
    }
