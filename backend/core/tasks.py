import re
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .celery import TenantTask
from .events import maybe_publish_audit_event, maybe_publish_event
from .logging import get_correlation_id, get_request_id, get_tenant_id, get_user_id
from .models import DataAsset, QualityCheckResult, QualityRule, RetentionHold, RetentionRun


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
