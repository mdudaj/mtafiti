import json
import time
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from core.models import UserNotification
from core.tasks import ping
from tenants.models import Domain, Tenant


def _create_tenant_host() -> tuple[str, str]:
    host = f'tenanta-{uuid.uuid4().hex[:6]}.example'
    with schema_context('public'):
        tenant = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f"Tenant A {uuid.uuid4().hex[:6]}",
        )
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()
    return host, tenant.schema_name


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(0.95 * len(ordered)) - 1))
    return ordered[index]


@pytest.mark.django_db(transaction=True)
def test_api_latency_baseline_profiles():
    host, tenant_schema = _create_tenant_host()
    client = Client()

    for idx in range(20):
        created = client.post(
            '/api/v1/assets',
            data=json.dumps({'qualified_name': f'db.table_{idx}', 'asset_type': 'table'}),
            content_type='application/json',
            HTTP_HOST=host,
        )
        assert created.status_code == 201

    health_latencies: list[float] = []
    list_latencies: list[float] = []
    paginated_list_latencies: list[float] = []
    error_count = 0

    for _ in range(40):
        start = time.perf_counter()
        response = client.get('/healthz', HTTP_HOST='unknown.example')
        health_latencies.append(time.perf_counter() - start)
        if response.status_code >= 500:
            error_count += 1

    for _ in range(40):
        start = time.perf_counter()
        response = client.get('/api/v1/assets', HTTP_HOST=host)
        list_latencies.append(time.perf_counter() - start)
        if response.status_code >= 500:
            error_count += 1

    for _ in range(40):
        start = time.perf_counter()
        response = client.get('/api/v1/assets?page=1&page_size=20', HTTP_HOST=host)
        paginated_list_latencies.append(time.perf_counter() - start)
        if response.status_code >= 500:
            error_count += 1

    with schema_context(tenant_schema):
        for idx in range(200):
            UserNotification.objects.create(
                user_email=f'user{idx}@example.com',
                notification_type='ops_alert',
                channel=UserNotification.Channel.EMAIL,
                delivery_status=UserNotification.DeliveryStatus.PENDING,
                payload={'seq': idx},
            )

    notification_list_latencies: list[float] = []
    for _ in range(40):
        start = time.perf_counter()
        response = client.get(
            '/api/v1/notifications?status=pending&page=1&page_size=50',
            HTTP_HOST=host,
        )
        notification_list_latencies.append(time.perf_counter() - start)
        if response.status_code >= 500:
            error_count += 1

    assert error_count == 0
    assert _p95(health_latencies) < 0.100
    assert _p95(list_latencies) < 0.300
    assert _p95(paginated_list_latencies) < 0.250
    assert _p95(notification_list_latencies) < 0.300


@pytest.mark.django_db(transaction=True)
def test_worker_latency_baseline_profile():
    _, tenant_schema = _create_tenant_host()
    client = Client()
    run_latencies: list[float] = []

    for _ in range(30):
        start = time.perf_counter()
        result = ping.apply(kwargs={'tenant_schema': tenant_schema})
        run_latencies.append(time.perf_counter() - start)
        assert result.get() == f'pong:{tenant_schema}'

    assert _p95(run_latencies) < 0.200

    metrics = client.get('/metrics', HTTP_HOST='unknown.example')
    body = metrics.content.decode('utf-8')
    assert 'edmp_celery_task_executions_total' in body
    assert 'core.tasks.ping' in body
