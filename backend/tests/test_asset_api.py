import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

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
