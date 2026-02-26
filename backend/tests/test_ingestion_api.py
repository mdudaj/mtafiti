import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

import core.events as events
from tenants.models import Domain, Tenant


@pytest.mark.django_db(transaction=True)
def test_ingestion_create_and_get_is_tenant_scoped():
    host_a = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    host_b = f"tenantb-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant_a = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant A {uuid.uuid4().hex[:6]}")
        tenant_a.save()
        Domain(domain=host_a, tenant=tenant_a, is_primary=True).save()

        tenant_b = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant B {uuid.uuid4().hex[:6]}")
        tenant_b.save()
        Domain(domain=host_b, tenant=tenant_b, is_primary=True).save()

    client = Client()
    created = client.post(
        '/api/v1/ingestions',
        data=json.dumps({'connector': 'dbt', 'source': {'project': 'x'}}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    body = created.json()
    assert body['connector'] == 'dbt'
    assert body['status'] == 'queued'

    got = client.get(f"/api/v1/ingestions/{body['id']}", HTTP_HOST=host_a)
    assert got.status_code == 200
    assert got.json()['id'] == body['id']

    missing = client.get(f"/api/v1/ingestions/{body['id']}", HTTP_HOST=host_b)
    assert missing.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_ingestion_create_validates_payload():
    host = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant A {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()

    client = Client()
    missing_connector = client.post(
        '/api/v1/ingestions',
        data=json.dumps({'source': {'x': 1}}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert missing_connector.status_code == 400

    invalid_source = client.post(
        '/api/v1/ingestions',
        data=json.dumps({'connector': 'dbt', 'source': 'nope'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert invalid_source.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_ingestion_create_emits_domain_and_audit_events_when_configured(monkeypatch):
    calls = []

    def fake_publish_event(*, exchange, routing_key, payload, rabbitmq_url=None):
        calls.append({'exchange': exchange, 'routing_key': routing_key, 'payload': payload, 'rabbitmq_url': rabbitmq_url})

    monkeypatch.setattr(events, 'publish_event', fake_publish_event)
    monkeypatch.setenv('RABBITMQ_URL', 'amqp://test/')
    monkeypatch.setenv('EDMP_EVENT_EXCHANGE', 'edmp.events')

    host = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant A {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()

    client = Client()
    created = client.post(
        '/api/v1/ingestions',
        data=json.dumps({'connector': 'dbt', 'source': {'project': 'x'}}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_CORRELATION_ID='corr-1',
        HTTP_X_USER_ID='user-1',
    )
    assert created.status_code == 201

    assert [c['routing_key'] for c in calls] == [
        f'{tenant.schema_name}.ingestion.created',
        f'{tenant.schema_name}.audit.ingestion.created',
    ]
    assert calls[0]['payload']['event_type'] == 'ingestion.created'
    assert calls[1]['payload']['event_type'] == 'audit.ingestion.created'
