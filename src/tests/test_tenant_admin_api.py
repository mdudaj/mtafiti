import json
import uuid

import pytest
from django.test import Client

import core.events as events


@pytest.mark.django_db(transaction=True)
def test_tenant_admin_api_can_create_tenant_and_route_requests():
    host = f"tenant-{uuid.uuid4().hex[:6]}.example"
    control_host = 'control.example'

    client = Client()
    created = client.post(
        '/api/v1/tenants',
        data=json.dumps({'name': f"Tenant {uuid.uuid4().hex[:6]}", 'domain': host}),
        content_type='application/json',
        HTTP_HOST=control_host,
    )
    assert created.status_code == 201
    schema_name = created.json()['schema_name']

    tenants = client.get('/api/v1/tenants', HTTP_HOST=control_host)
    assert tenants.status_code == 200
    assert any(t['schema_name'] == schema_name for t in tenants.json()['items'])

    routed = client.get('/', HTTP_HOST=host)
    assert routed.status_code == 200
    assert routed.json()['schema'] == schema_name


@pytest.mark.django_db(transaction=True)
def test_tenant_admin_api_normalizes_domain():
    host = f"tenant-{uuid.uuid4().hex[:6]}.example"
    control_host = 'control.example'

    client = Client()
    created = client.post(
        '/api/v1/tenants',
        data=json.dumps({'name': f'Tenant {uuid.uuid4().hex[:6]}', 'domain': f'https://{host.upper()}:8443/some/path'}),
        content_type='application/json',
        HTTP_HOST=control_host,
    )
    assert created.status_code == 201
    assert created.json()['domains'] == [host]

    routed = client.get('/', HTTP_HOST=host)
    assert routed.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_tenant_create_emits_event_when_configured(monkeypatch):
    calls = []

    def fake_publish_event(*, exchange, routing_key, payload, rabbitmq_url=None):
        calls.append({'exchange': exchange, 'routing_key': routing_key, 'payload': payload, 'rabbitmq_url': rabbitmq_url})

    monkeypatch.setattr(events, 'publish_event', fake_publish_event)
    monkeypatch.setenv('RABBITMQ_URL', 'amqp://test/')
    monkeypatch.setenv('EDMP_EVENT_EXCHANGE', 'edmp.events')

    host = f"tenant-{uuid.uuid4().hex[:6]}.example"
    control_host = 'control.example'

    client = Client()
    created = client.post(
        '/api/v1/tenants',
        data=json.dumps({'name': f"Tenant {uuid.uuid4().hex[:6]}", 'domain': host}),
        content_type='application/json',
        HTTP_HOST=control_host,
        HTTP_X_CORRELATION_ID='corr-1',
        HTTP_X_USER_ID='user-1',
    )
    assert created.status_code == 201
    schema_name = created.json()['schema_name']

    assert [c['routing_key'] for c in calls] == [
        f'{schema_name}.control.tenant.created',
        f'{schema_name}.audit.tenant.created',
    ]
    assert calls[0]['payload']['event_type'] == 'tenant.created'
    assert calls[0]['payload']['tenant_id'] == schema_name
    assert calls[0]['payload']['correlation_id'] == 'corr-1'
    assert calls[0]['payload']['user_id'] == 'user-1'
    assert calls[1]['payload']['event_type'] == 'audit.tenant.created'


@pytest.mark.django_db(transaction=True)
def test_tenant_services_registry_create_and_list():
    client = Client()
    control_host = 'control.example'
    created_tenant = client.post(
        '/api/v1/tenants',
        data=json.dumps({'name': f'Tenant {uuid.uuid4().hex[:6]}', 'domain': f"tenant-{uuid.uuid4().hex[:6]}.example"}),
        content_type='application/json',
        HTTP_HOST=control_host,
    )
    assert created_tenant.status_code == 201
    tenant_id = created_tenant.json()['id']

    created_route = client.post(
        '/api/v1/tenants/services',
        data=json.dumps(
            {
                'tenant_id': tenant_id,
                'service_key': 'printing',
                'tenant_slug': 'tenant-alpha',
                'base_domain': 'platform.example.com',
                'workspace_path': '/app',
            }
        ),
        content_type='application/json',
        HTTP_HOST=control_host,
    )
    assert created_route.status_code == 201
    assert created_route.json()['domain'] == 'printing.tenant-alpha.platform.example.com'

    listed = client.get(
        f'/api/v1/tenants/services?tenant_id={tenant_id}',
        HTTP_HOST=control_host,
    )
    assert listed.status_code == 200
    assert len(listed.json()['items']) == 1
