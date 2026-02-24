import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

import core.events as events
from tenants.models import Domain, Tenant


@pytest.mark.django_db(transaction=True)
def test_asset_create_and_list_is_tenant_scoped():
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
    resp = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.table', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert resp.status_code == 201
    asset_id = resp.json()['id']

    list_a = client.get('/api/v1/assets', HTTP_HOST=host_a)
    assert list_a.status_code == 200
    assert [a['id'] for a in list_a.json()['items']] == [asset_id]

    list_b = client.get('/api/v1/assets', HTTP_HOST=host_b)
    assert list_b.status_code == 200
    assert list_b.json()['items'] == []


@pytest.mark.django_db(transaction=True)
def test_asset_update_roundtrip():
    host = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant A {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()

    client = Client()
    created_resp = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.table', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created_resp.status_code == 201
    created = created_resp.json()

    resp = client.put(
        f"/api/v1/assets/{created['id']}",
        data=json.dumps({'display_name': 'Table', 'properties': {'owner': 'data-team'}}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert resp.status_code == 200
    assert resp.json()['display_name'] == 'Table'
    assert resp.json()['properties']['owner'] == 'data-team'

    removed = client.put(
        f"/api/v1/assets/{created['id']}",
        data=json.dumps({'properties': {'owner': None}}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert removed.status_code == 200
    assert 'owner' not in removed.json()['properties']

    multi = client.put(
        f"/api/v1/assets/{created['id']}",
        data=json.dumps({'properties': {'missing': None, 'env': 'prod'}}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert multi.status_code == 200
    assert multi.json()['properties']['env'] == 'prod'
    assert 'missing' not in multi.json()['properties']

    cannot_change_type = client.put(
        f"/api/v1/assets/{created['id']}",
        data=json.dumps({'asset_type': 'view'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert cannot_change_type.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_asset_mutations_emit_events_when_configured(monkeypatch):
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
    created_resp = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.table', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_CORRELATION_ID='corr-1',
        HTTP_X_USER_ID='user-1',
    )
    assert created_resp.status_code == 201
    created = created_resp.json()

    updated_resp = client.put(
        f"/api/v1/assets/{created['id']}",
        data=json.dumps({'display_name': 'Table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_CORRELATION_ID='corr-1',
        HTTP_X_USER_ID='user-1',
    )
    assert updated_resp.status_code == 200

    assert [c['routing_key'] for c in calls] == [
        f'{tenant.schema_name}.catalog.asset.created',
        f'{tenant.schema_name}.catalog.asset.updated',
    ]
    assert calls[0]['payload']['event_type'] == 'asset.created'
    assert calls[0]['payload']['tenant_id'] == tenant.schema_name
    assert calls[0]['payload']['correlation_id'] == 'corr-1'
    assert calls[0]['payload']['user_id'] == 'user-1'


@pytest.mark.django_db(transaction=True)
def test_asset_optional_catalog_fields_roundtrip_and_validation():
    host = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant A {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()

    client = Client()
    created_resp = client.post(
        '/api/v1/assets',
        data=json.dumps(
            {
                'qualified_name': 'db.dataset',
                'asset_type': 'table',
                'description': 'Main dataset',
                'owner': 'data-platform',
                'tags': ['gold'],
                'classifications': ['pii'],
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created_resp.status_code == 201
    created = created_resp.json()
    assert created['description'] == 'Main dataset'
    assert created['owner'] == 'data-platform'
    assert created['tags'] == ['gold']
    assert created['classifications'] == ['pii']

    updated_resp = client.put(
        f"/api/v1/assets/{created['id']}",
        data=json.dumps({'description': None, 'owner': None, 'tags': None, 'classifications': ['internal']}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert updated_resp.status_code == 200
    updated = updated_resp.json()
    assert updated['description'] is None
    assert updated['owner'] is None
    assert updated['tags'] == []
    assert updated['classifications'] == ['internal']

    invalid_tags = client.put(
        f"/api/v1/assets/{created['id']}",
        data=json.dumps({'tags': ['ok', 123]}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert invalid_tags.status_code == 400
