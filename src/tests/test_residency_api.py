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
def test_residency_profile_lifecycle_and_check():
    host, _ = _create_tenants()
    client = Client()
    created = client.post(
        '/api/v1/residency/profiles',
        data=json.dumps(
            {
                'name': 'EU-only',
                'allowed_regions': ['eu-west-1', 'eu-central-1'],
                'blocked_regions': ['us-east-1'],
                'enforcement_mode': 'enforced',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    profile_id = created.json()['id']
    assert created.json()['status'] == 'draft'

    listed = client.get('/api/v1/residency/profiles', HTTP_HOST=host)
    assert listed.status_code == 200
    assert len(listed.json()['items']) == 1

    activated = client.post(f'/api/v1/residency/profiles/{profile_id}/activate', HTTP_HOST=host)
    assert activated.status_code == 200
    assert activated.json()['status'] == 'active'

    allowed = client.post(
        '/api/v1/residency/check',
        data=json.dumps({'profile_id': profile_id, 'target_region': 'eu-west-1'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert allowed.status_code == 200
    assert allowed.json()['allowed'] is True

    denied = client.post(
        '/api/v1/residency/check',
        data=json.dumps({'profile_id': profile_id, 'target_region': 'us-east-1'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert denied.status_code == 403
    assert denied.json()['allowed'] is False
    assert denied.json()['reason'] == 'blocked_region'

    deprecated = client.post(f'/api/v1/residency/profiles/{profile_id}/deprecate', HTTP_HOST=host)
    assert deprecated.status_code == 200
    assert deprecated.json()['status'] == 'deprecated'


@pytest.mark.django_db(transaction=True)
def test_residency_is_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    created = client.post(
        '/api/v1/residency/profiles',
        data=json.dumps({'name': 'Tenant A residency', 'allowed_regions': ['eu-west-1']}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    profile_id = created.json()['id']

    assert len(client.get('/api/v1/residency/profiles', HTTP_HOST=host_a).json()['items']) == 1
    assert client.get('/api/v1/residency/profiles', HTTP_HOST=host_b).json()['items'] == []
    assert client.get(f'/api/v1/residency/profiles/{profile_id}', HTTP_HOST=host_b).status_code == 404
    assert (
        client.post(
            '/api/v1/residency/check',
            data=json.dumps({'profile_id': profile_id, 'target_region': 'eu-west-1'}),
            content_type='application/json',
            HTTP_HOST=host_b,
        ).status_code
        == 404
    )


@pytest.mark.django_db(transaction=True)
def test_residency_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _ = _create_tenants()
    client = Client()

    denied_create = client.post(
        '/api/v1/residency/profiles',
        data=json.dumps({'name': 'P', 'allowed_regions': ['eu-west-1']}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_create.status_code == 403

    created = client.post(
        '/api/v1/residency/profiles',
        data=json.dumps({'name': 'P', 'allowed_regions': ['eu-west-1'], 'enforcement_mode': 'advisory'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='policy.admin',
    )
    assert created.status_code == 201
    profile_id = created.json()['id']

    denied_read = client.get('/api/v1/residency/profiles', HTTP_HOST=host)
    assert denied_read.status_code == 403
    allowed_read = client.get('/api/v1/residency/profiles', HTTP_HOST=host, HTTP_X_USER_ROLES='catalog.reader')
    assert allowed_read.status_code == 200

    denied_activate = client.post(
        f'/api/v1/residency/profiles/{profile_id}/activate',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_activate.status_code == 403
    allowed_activate = client.post(
        f'/api/v1/residency/profiles/{profile_id}/activate',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed_activate.status_code == 200

    denied_check = client.post(
        '/api/v1/residency/check',
        data=json.dumps({'profile_id': profile_id, 'target_region': 'eu-west-1'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert denied_check.status_code == 403
    allowed_check = client.post(
        '/api/v1/residency/check',
        data=json.dumps({'profile_id': profile_id, 'target_region': 'eu-west-1'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert allowed_check.status_code == 200
