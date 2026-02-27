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
def test_classification_lifecycle_and_asset_assignment():
    host, _ = _create_tenants()
    client = Client()

    created = client.post(
        '/api/v1/classifications',
        data=json.dumps(
            {
                'name': 'restricted',
                'level': 'restricted',
                'description': 'Contains personal data',
                'tags': ['privacy', 'gdpr'],
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    classification_id = created.json()['id']
    assert created.json()['status'] == 'draft'

    active = client.post(
        f'/api/v1/classifications/{classification_id}/activate',
        HTTP_HOST=host,
    )
    assert active.status_code == 200
    assert active.json()['status'] == 'active'

    asset = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.customers', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert asset.status_code == 201
    asset_id = asset.json()['id']

    assigned = client.post(
        f'/api/v1/assets/{asset_id}/classifications',
        data=json.dumps({'classifications': ['restricted']}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert assigned.status_code == 200
    assert assigned.json()['classifications'] == ['restricted']

    deprecated = client.post(
        f'/api/v1/classifications/{classification_id}/deprecate',
        HTTP_HOST=host,
    )
    assert deprecated.status_code == 200
    assert deprecated.json()['status'] == 'deprecated'

    blocked = client.post(
        f'/api/v1/assets/{asset_id}/classifications',
        data=json.dumps({'classifications': ['restricted']}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert blocked.status_code == 400
    assert blocked.json()['error'] == 'inactive_or_unknown_classifications'


@pytest.mark.django_db(transaction=True)
def test_classification_is_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()

    created = client.post(
        '/api/v1/classifications',
        data=json.dumps({'name': 'internal-only', 'level': 'internal'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    classification_id = created.json()['id']

    list_a = client.get('/api/v1/classifications', HTTP_HOST=host_a)
    assert list_a.status_code == 200
    assert len(list_a.json()['items']) == 1

    list_b = client.get('/api/v1/classifications', HTTP_HOST=host_b)
    assert list_b.status_code == 200
    assert list_b.json()['items'] == []

    detail_b = client.get(
        f'/api/v1/classifications/{classification_id}',
        HTTP_HOST=host_b,
    )
    assert detail_b.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_classification_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _ = _create_tenants()
    client = Client()

    denied_create = client.post(
        '/api/v1/classifications',
        data=json.dumps({'name': 'restricted', 'level': 'restricted'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_create.status_code == 403

    created = client.post(
        '/api/v1/classifications',
        data=json.dumps({'name': 'restricted', 'level': 'restricted'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='policy.admin',
    )
    assert created.status_code == 201
    classification_id = created.json()['id']

    denied_activate = client.post(
        f'/api/v1/classifications/{classification_id}/activate',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_activate.status_code == 403

    allowed_activate = client.post(
        f'/api/v1/classifications/{classification_id}/activate',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed_activate.status_code == 200

    asset = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.customers', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    asset_id = asset.json()['id']

    denied_assignment = client.post(
        f'/api/v1/assets/{asset_id}/classifications',
        data=json.dumps({'classifications': ['restricted']}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert denied_assignment.status_code == 403

    allowed_assignment = client.post(
        f'/api/v1/assets/{asset_id}/classifications',
        data=json.dumps({'classifications': ['restricted']}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor,policy.admin',
    )
    assert allowed_assignment.status_code == 200

    denied_read = client.get('/api/v1/classifications', HTTP_HOST=host)
    assert denied_read.status_code == 403
    allowed_read = client.get(
        '/api/v1/classifications',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert allowed_read.status_code == 200
