import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


def _create_tenant_hosts():
    host_a = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    host_b = f"tenantb-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant_a = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant A {uuid.uuid4().hex[:6]}")
        tenant_a.save()
        Domain(domain=host_a, tenant=tenant_a, is_primary=True).save()
        tenant_b = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant B {uuid.uuid4().hex[:6]}")
        tenant_b.save()
        Domain(domain=host_b, tenant=tenant_b, is_primary=True).save()
    return host_a, host_b


@pytest.mark.django_db(transaction=True)
def test_data_contract_create_get_list_and_asset_list():
    host, _ = _create_tenant_hosts()
    client = Client()
    created_asset = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created_asset.status_code == 201
    asset_id = created_asset.json()['id']

    contract = client.post(
        '/api/v1/contracts',
        data=json.dumps(
            {
                'asset_id': asset_id,
                'schema': {'fields': [{'name': 'order_id', 'type': 'string', 'nullable': False}]},
                'expectations': [{'type': 'required', 'field': 'order_id'}],
                'owners': ['data-team'],
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert contract.status_code == 201
    contract_id = contract.json()['id']
    assert contract.json()['version'] == 1
    assert contract.json()['status'] == 'draft'

    fetched = client.get(f'/api/v1/contracts/{contract_id}', HTTP_HOST=host)
    assert fetched.status_code == 200
    assert fetched.json()['id'] == contract_id

    all_contracts = client.get('/api/v1/contracts', HTTP_HOST=host)
    assert all_contracts.status_code == 200
    assert len(all_contracts.json()['items']) == 1

    by_asset = client.get(f'/api/v1/assets/{asset_id}/contracts', HTTP_HOST=host)
    assert by_asset.status_code == 200
    assert len(by_asset.json()['items']) == 1


@pytest.mark.django_db(transaction=True)
def test_data_contract_versions_activation_and_deprecation():
    host, _ = _create_tenant_hosts()
    client = Client()
    created_asset = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    asset_id = created_asset.json()['id']

    c1 = client.post('/api/v1/contracts', data=json.dumps({'asset_id': asset_id}), content_type='application/json', HTTP_HOST=host)
    c2 = client.post('/api/v1/contracts', data=json.dumps({'asset_id': asset_id}), content_type='application/json', HTTP_HOST=host)
    assert c1.status_code == 201
    assert c2.status_code == 201
    assert c1.json()['version'] == 1
    assert c2.json()['version'] == 2

    activate1 = client.post(f"/api/v1/contracts/{c1.json()['id']}/activate", HTTP_HOST=host)
    assert activate1.status_code == 200
    assert activate1.json()['status'] == 'active'

    activate2 = client.post(f"/api/v1/contracts/{c2.json()['id']}/activate", HTTP_HOST=host)
    assert activate2.status_code == 200
    assert activate2.json()['status'] == 'active'

    refreshed1 = client.get(f"/api/v1/contracts/{c1.json()['id']}", HTTP_HOST=host)
    assert refreshed1.status_code == 200
    assert refreshed1.json()['status'] == 'deprecated'

    deprecated2 = client.post(f"/api/v1/contracts/{c2.json()['id']}/deprecate", HTTP_HOST=host)
    assert deprecated2.status_code == 200
    assert deprecated2.json()['status'] == 'deprecated'


@pytest.mark.django_db(transaction=True)
def test_data_contract_endpoints_are_tenant_scoped():
    host_a, host_b = _create_tenant_hosts()
    client = Client()
    asset_a = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    contract = client.post(
        '/api/v1/contracts',
        data=json.dumps({'asset_id': asset_a.json()['id']}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert contract.status_code == 201
    contract_id = contract.json()['id']

    assert client.get('/api/v1/contracts', HTTP_HOST=host_b).json()['items'] == []
    assert client.get(f'/api/v1/contracts/{contract_id}', HTTP_HOST=host_b).status_code == 404
    assert client.post(f'/api/v1/contracts/{contract_id}/activate', HTTP_HOST=host_b).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_data_contract_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _ = _create_tenant_hosts()
    client = Client()
    created_asset = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    asset_id = created_asset.json()['id']

    denied_create = client.post('/api/v1/contracts', data=json.dumps({'asset_id': asset_id}), content_type='application/json', HTTP_HOST=host)
    assert denied_create.status_code == 403

    allowed_create = client.post(
        '/api/v1/contracts',
        data=json.dumps({'asset_id': asset_id}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert allowed_create.status_code == 201
    contract_id = allowed_create.json()['id']

    denied_read = client.get('/api/v1/contracts', HTTP_HOST=host)
    assert denied_read.status_code == 403
    allowed_read = client.get('/api/v1/contracts', HTTP_HOST=host, HTTP_X_USER_ROLES='catalog.reader')
    assert allowed_read.status_code == 200

    denied_activate = client.post(f'/api/v1/contracts/{contract_id}/activate', HTTP_HOST=host, HTTP_X_USER_ROLES='catalog.editor')
    assert denied_activate.status_code == 403
    allowed_activate = client.post(f'/api/v1/contracts/{contract_id}/activate', HTTP_HOST=host, HTTP_X_USER_ROLES='policy.admin')
    assert allowed_activate.status_code == 200
