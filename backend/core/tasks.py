from celery import shared_task
from django.utils import timezone

from .celery import TenantTask
from .events import maybe_publish_audit_event, maybe_publish_event
from .logging import get_correlation_id, get_request_id, get_tenant_id, get_user_id
from .models import QualityCheckResult, QualityRule


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
