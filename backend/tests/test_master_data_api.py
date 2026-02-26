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
        tenant_a = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f"Tenant A {uuid.uuid4().hex[:6]}",
        )
        tenant_a.save()
        Domain(domain=host_a, tenant=tenant_a, is_primary=True).save()
        tenant_b = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f"Tenant B {uuid.uuid4().hex[:6]}",
        )
        tenant_b.save()
        Domain(domain=host_b, tenant=tenant_b, is_primary=True).save()
    return host_a, host_b


@pytest.mark.django_db(transaction=True)
def test_master_data_record_and_merge_lifecycle():
    host, _ = _create_tenants()
    client = Client()

    created = client.post(
        '/api/v1/master-data/customer/records',
        data=json.dumps(
            {
                'attributes': {'name': 'Acme', 'country': 'DE'},
                'survivorship_policy': {'name': 'latest-non-null'},
                'confidence': 0.92,
                'status': 'active',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    master_id = created.json()['master_id']
    assert created.json()['version'] == 1

    updated = client.post(
        '/api/v1/master-data/customer/records',
        data=json.dumps(
            {
                'master_id': master_id,
                'attributes': {'name': 'Acme GmbH', 'country': 'DE'},
                'survivorship_policy': {'name': 'latest-non-null'},
                'status': 'active',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert updated.status_code == 201
    assert updated.json()['version'] == 2

    latest = client.get(
        f'/api/v1/master-data/customer/records/{master_id}',
        HTTP_HOST=host,
    )
    assert latest.status_code == 200
    assert latest.json()['version'] == 2
    assert latest.json()['attributes']['name'] == 'Acme GmbH'

    v1 = client.get(
        f'/api/v1/master-data/customer/records/{master_id}?version=1',
        HTTP_HOST=host,
    )
    assert v1.status_code == 200
    assert v1.json()['attributes']['name'] == 'Acme'

    candidate = client.post(
        '/api/v1/master-data/customer/merge-candidates',
        data=json.dumps(
            {
                'target_master_id': master_id,
                'source_master_refs': ['crm:42', 'erp:201'],
                'proposed_attributes': {'name': 'Acme AG', 'country': 'DE'},
                'confidence': 0.78,
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert candidate.status_code == 201
    candidate_id = candidate.json()['id']

    approved = client.post(
        f'/api/v1/master-data/customer/merge-candidates/{candidate_id}/approve',
        HTTP_HOST=host,
    )
    assert approved.status_code == 200
    assert approved.json()['candidate']['status'] == 'approved'
    assert approved.json()['record']['version'] == 3
    assert approved.json()['record']['attributes']['name'] == 'Acme AG'


@pytest.mark.django_db(transaction=True)
def test_master_data_is_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    created = client.post(
        '/api/v1/master-data/customer/records',
        data=json.dumps({'attributes': {'name': 'Acme'}, 'status': 'active'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    master_id = created.json()['master_id']

    list_a = client.get('/api/v1/master-data/customer/records', HTTP_HOST=host_a)
    assert list_a.status_code == 200
    assert len(list_a.json()['items']) == 1

    list_b = client.get('/api/v1/master-data/customer/records', HTTP_HOST=host_b)
    assert list_b.status_code == 200
    assert list_b.json()['items'] == []

    detail_b = client.get(
        f'/api/v1/master-data/customer/records/{master_id}',
        HTTP_HOST=host_b,
    )
    assert detail_b.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_master_data_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _ = _create_tenants()
    client = Client()

    denied_create = client.post(
        '/api/v1/master-data/customer/records',
        data=json.dumps({'attributes': {'name': 'Acme'}, 'status': 'active'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_create.status_code == 403

    created = client.post(
        '/api/v1/master-data/customer/records',
        data=json.dumps({'attributes': {'name': 'Acme'}, 'status': 'active'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='policy.admin',
    )
    assert created.status_code == 201
    master_id = created.json()['master_id']

    denied_merge_candidate = client.post(
        '/api/v1/master-data/customer/merge-candidates',
        data=json.dumps(
            {
                'target_master_id': master_id,
                'proposed_attributes': {'name': 'Acme AG'},
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_merge_candidate.status_code == 403

    allowed_merge_candidate = client.post(
        '/api/v1/master-data/customer/merge-candidates',
        data=json.dumps(
            {
                'target_master_id': master_id,
                'proposed_attributes': {'name': 'Acme AG'},
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed_merge_candidate.status_code == 201

    candidate_id = allowed_merge_candidate.json()['id']
    denied_approve = client.post(
        f'/api/v1/master-data/customer/merge-candidates/{candidate_id}/approve',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_approve.status_code == 403
    allowed_approve = client.post(
        f'/api/v1/master-data/customer/merge-candidates/{candidate_id}/approve',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='policy.admin',
    )
    assert allowed_approve.status_code == 200

    denied_read = client.get('/api/v1/master-data/customer/records', HTTP_HOST=host)
    assert denied_read.status_code == 403
    allowed_read = client.get(
        '/api/v1/master-data/customer/records',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert allowed_read.status_code == 200
