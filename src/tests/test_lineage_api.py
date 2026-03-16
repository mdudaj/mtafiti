import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

import core.events as events
from tenants.models import Domain, Tenant


@pytest.mark.django_db(transaction=True)
def test_lineage_edge_upsert_and_query_is_tenant_scoped():
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
    a = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.a', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    ).json()['id']
    b = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.b', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    ).json()['id']
    c = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.c', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    ).json()['id']

    upserted = client.post(
        '/api/v1/lineage/edges',
        data=json.dumps(
            {
                'items': [
                    {'from_asset_id': a, 'to_asset_id': b, 'edge_type': 'derived_from'},
                    {'from_asset_id': b, 'to_asset_id': c, 'edge_type': 'derived_from'},
                ]
            }
        ),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert upserted.status_code == 200
    assert len(upserted.json()['items']) == 2

    downstream = client.get(
        f'/api/v1/lineage/edges?asset_id={a}&direction=downstream&depth=2',
        HTTP_HOST=host_a,
    )
    assert downstream.status_code == 200
    assert {e['from_asset_id'] for e in downstream.json()['edges']} == {a, b}
    assert {e['to_asset_id'] for e in downstream.json()['edges']} == {b, c}
    assert {x['id'] for x in downstream.json()['assets']} >= {a, b, c}

    upstream = client.get(
        f'/api/v1/lineage/edges?asset_id={c}&direction=upstream&depth=2',
        HTTP_HOST=host_a,
    )
    assert upstream.status_code == 200
    assert {e['from_asset_id'] for e in upstream.json()['edges']} == {a, b}
    assert {e['to_asset_id'] for e in upstream.json()['edges']} == {b, c}

    missing = client.get(
        f'/api/v1/lineage/edges?asset_id={a}&direction=downstream&depth=1',
        HTTP_HOST=host_b,
    )
    assert missing.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_lineage_edge_upsert_updates_existing_edge():
    host = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant A {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()

    client = Client()
    a = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.a', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    ).json()['id']
    b = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.b', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    ).json()['id']

    created = client.post(
        '/api/v1/lineage/edges',
        data=json.dumps({'items': [{'from_asset_id': a, 'to_asset_id': b, 'edge_type': 'reads_from', 'properties': {'w': 1}}]}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created.status_code == 200
    edge_id = created.json()['items'][0]['id']

    updated = client.post(
        '/api/v1/lineage/edges',
        data=json.dumps({'items': [{'from_asset_id': a, 'to_asset_id': b, 'edge_type': 'reads_from', 'properties': {'w': 2}}]}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert updated.status_code == 200
    assert updated.json()['items'][0]['id'] == edge_id
    assert updated.json()['items'][0]['properties']['w'] == 2


@pytest.mark.django_db(transaction=True)
def test_lineage_edge_upsert_emits_event_when_configured(monkeypatch):
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
    a = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.a', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    ).json()['id']
    b = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.b', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    ).json()['id']

    calls.clear()

    upserted = client.post(
        '/api/v1/lineage/edges',
        data=json.dumps({'items': [{'from_asset_id': a, 'to_asset_id': b, 'edge_type': 'reads_from'}]}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_CORRELATION_ID='corr-1',
        HTTP_X_USER_ID='user-1',
    )
    assert upserted.status_code == 200

    assert [c['routing_key'] for c in calls] == [
        f'{tenant.schema_name}.lineage.edge.upserted',
        f'{tenant.schema_name}.audit.lineage.edge.upserted',
    ]
    assert calls[0]['payload']['event_type'] == 'lineage.edge.upserted'
    assert calls[0]['payload']['tenant_id'] == tenant.schema_name
    assert calls[0]['payload']['correlation_id'] == 'corr-1'
    assert calls[0]['payload']['user_id'] == 'user-1'
    assert len(calls[0]['payload']['data']['items']) == 1
    assert calls[1]['payload']['event_type'] == 'audit.lineage.edge.upserted'
