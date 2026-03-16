import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


def _create_tenants():
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
def test_reference_data_dataset_and_version_lifecycle():
    host, _ = _create_tenants()
    client = Client()
    created_dataset = client.post(
        '/api/v1/reference-data/datasets',
        data=json.dumps({'name': 'country-codes', 'owner': 'steward@example.com', 'domain': 'compliance'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created_dataset.status_code == 201
    dataset_id = created_dataset.json()['id']

    v1 = client.post(
        f'/api/v1/reference-data/datasets/{dataset_id}/versions',
        data=json.dumps({'values': [{'code': 'DE'}, {'code': 'PL'}], 'status': 'approved'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert v1.status_code == 201
    assert v1.json()['version'] == 1

    v2 = client.post(
        f'/api/v1/reference-data/datasets/{dataset_id}/versions',
        data=json.dumps({'values': [{'code': 'DE'}, {'code': 'PL'}, {'code': 'FR'}]}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert v2.status_code == 201
    assert v2.json()['version'] == 2

    activated_v1 = client.post(
        f'/api/v1/reference-data/datasets/{dataset_id}/versions/1/activate',
        HTTP_HOST=host,
    )
    assert activated_v1.status_code == 200
    assert activated_v1.json()['status'] == 'active'

    activated_v2 = client.post(
        f'/api/v1/reference-data/datasets/{dataset_id}/versions/2/activate',
        HTTP_HOST=host,
    )
    assert activated_v2.status_code == 200
    assert activated_v2.json()['status'] == 'active'

    listed = client.get('/api/v1/reference-data/datasets', HTTP_HOST=host)
    assert listed.status_code == 200
    assert listed.json()['items'][0]['active_version'] == 2

    values = client.get(f'/api/v1/reference-data/datasets/{dataset_id}/versions/2/values', HTTP_HOST=host)
    assert values.status_code == 200
    assert len(values.json()['values']) == 3


@pytest.mark.django_db(transaction=True)
def test_reference_data_is_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    created = client.post(
        '/api/v1/reference-data/datasets',
        data=json.dumps({'name': 'country-codes', 'owner': 'steward@example.com'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    dataset_id = created.json()['id']

    created_version = client.post(
        f'/api/v1/reference-data/datasets/{dataset_id}/versions',
        data=json.dumps({'values': [{'code': 'DE'}]}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created_version.status_code == 201

    assert len(client.get('/api/v1/reference-data/datasets', HTTP_HOST=host_a).json()['items']) == 1
    assert client.get('/api/v1/reference-data/datasets', HTTP_HOST=host_b).json()['items'] == []
    assert client.post(f'/api/v1/reference-data/datasets/{dataset_id}/versions/1/activate', HTTP_HOST=host_b).status_code == 404
    assert client.get(f'/api/v1/reference-data/datasets/{dataset_id}/versions/1/values', HTTP_HOST=host_b).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_reference_data_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _ = _create_tenants()
    client = Client()

    denied_create = client.post(
        '/api/v1/reference-data/datasets',
        data=json.dumps({'name': 'country-codes'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_create.status_code == 403

    created = client.post(
        '/api/v1/reference-data/datasets',
        data=json.dumps({'name': 'country-codes'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='policy.admin',
    )
    assert created.status_code == 201
    dataset_id = created.json()['id']

    denied_version = client.post(
        f'/api/v1/reference-data/datasets/{dataset_id}/versions',
        data=json.dumps({'values': []}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_version.status_code == 403
    allowed_version = client.post(
        f'/api/v1/reference-data/datasets/{dataset_id}/versions',
        data=json.dumps({'values': []}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed_version.status_code == 201

    denied_activate = client.post(
        f'/api/v1/reference-data/datasets/{dataset_id}/versions/1/activate',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_activate.status_code == 403
    allowed_activate = client.post(
        f'/api/v1/reference-data/datasets/{dataset_id}/versions/1/activate',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='policy.admin',
    )
    assert allowed_activate.status_code == 200

    denied_read = client.get('/api/v1/reference-data/datasets', HTTP_HOST=host)
    assert denied_read.status_code == 403
    allowed_read = client.get('/api/v1/reference-data/datasets', HTTP_HOST=host, HTTP_X_USER_ROLES='catalog.reader')
    assert allowed_read.status_code == 200
