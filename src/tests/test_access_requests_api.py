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
def test_access_request_lifecycle():
    host, _ = _create_tenants()
    client = Client()
    created = client.post(
        '/api/v1/access-requests',
        data=json.dumps(
            {
                'subject_ref': 'asset:db.orders',
                'requester': 'alice@example.com',
                'access_type': 'read',
                'justification': 'investigation',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    request_id = created.json()['id']
    assert created.json()['status'] == 'submitted'

    in_review = client.post(
        f'/api/v1/access-requests/{request_id}/decision',
        data=json.dumps({'status': 'in_review', 'approver': 'owner@example.com'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert in_review.status_code == 200
    assert in_review.json()['status'] == 'in_review'

    approved = client.post(
        f'/api/v1/access-requests/{request_id}/decision',
        data=json.dumps({'status': 'approved', 'expires_at': '2030-01-01T00:00:00Z'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert approved.status_code == 200
    assert approved.json()['status'] == 'approved'
    assert approved.json()['expires_at'] is not None

    listed = client.get('/api/v1/access-requests', HTTP_HOST=host)
    assert listed.status_code == 200
    assert len(listed.json()['items']) == 1

    by_status = client.get('/api/v1/access-requests?status=approved', HTTP_HOST=host)
    assert by_status.status_code == 200
    assert len(by_status.json()['items']) == 1

    revoked = client.post(
        f'/api/v1/access-requests/{request_id}/decision',
        data=json.dumps({'status': 'revoked'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert revoked.status_code == 200
    assert revoked.json()['status'] == 'revoked'


@pytest.mark.django_db(transaction=True)
def test_access_requests_are_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    created = client.post(
        '/api/v1/access-requests',
        data=json.dumps(
            {
                'subject_ref': 'asset:db.orders',
                'requester': 'alice@example.com',
                'access_type': 'read',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    request_id = created.json()['id']

    assert len(client.get('/api/v1/access-requests', HTTP_HOST=host_a).json()['items']) == 1
    assert client.get('/api/v1/access-requests', HTTP_HOST=host_b).json()['items'] == []
    assert (
        client.post(
            f'/api/v1/access-requests/{request_id}/decision',
            data=json.dumps({'status': 'approved'}),
            content_type='application/json',
            HTTP_HOST=host_b,
        ).status_code
        == 404
    )


@pytest.mark.django_db(transaction=True)
def test_access_requests_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _ = _create_tenants()
    client = Client()

    denied_create = client.post(
        '/api/v1/access-requests',
        data=json.dumps({'subject_ref': 'asset:db.orders', 'requester': 'a', 'access_type': 'read'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert denied_create.status_code == 403

    created = client.post(
        '/api/v1/access-requests',
        data=json.dumps({'subject_ref': 'asset:db.orders', 'requester': 'a', 'access_type': 'read'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert created.status_code == 201
    request_id = created.json()['id']

    denied_decision = client.post(
        f'/api/v1/access-requests/{request_id}/decision',
        data=json.dumps({'status': 'approved'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_decision.status_code == 403
    allowed_decision = client.post(
        f'/api/v1/access-requests/{request_id}/decision',
        data=json.dumps({'status': 'approved'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed_decision.status_code == 200

    denied_read = client.get('/api/v1/access-requests', HTTP_HOST=host)
    assert denied_read.status_code == 403
    allowed_read = client.get('/api/v1/access-requests', HTTP_HOST=host, HTTP_X_USER_ROLES='catalog.reader')
    assert allowed_read.status_code == 200
