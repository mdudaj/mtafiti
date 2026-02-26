import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from core.models import DataAsset
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
    return host_a, tenant_a.schema_name, host_b, tenant_b.schema_name


@pytest.mark.django_db(transaction=True)
def test_retention_rule_hold_and_run_lifecycle():
    host, schema, _, _ = _create_tenants()
    client = Client()
    a1 = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    ).json()['id']
    a2 = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.customers', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    ).json()['id']

    hold = client.post(
        '/api/v1/retention/holds',
        data=json.dumps({'asset_id': a2, 'reason': 'legal hold'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert hold.status_code == 201
    hold_id = hold.json()['id']

    created_rule = client.post(
        '/api/v1/retention/rules',
        data=json.dumps({'scope': {'asset_types': ['table']}, 'action': 'delete', 'retention_period': 'P0D'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created_rule.status_code == 201
    rule_id = created_rule.json()['id']

    dry = client.post(
        '/api/v1/retention/runs',
        data=json.dumps({'rule_id': rule_id, 'mode': 'dry_run'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert dry.status_code == 201
    assert dry.json()['result']['candidate_count'] == 1
    assert dry.json()['result']['held_count'] == 1
    assert dry.json()['result']['deleted_count'] == 0

    execute = client.post(
        '/api/v1/retention/runs',
        data=json.dumps({'rule_id': rule_id, 'mode': 'execute'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert execute.status_code == 201
    assert execute.json()['result']['deleted_count'] == 1
    assert execute.json()['result']['held_count'] == 1
    with schema_context(schema):
        assert DataAsset.objects.filter(id=a1).count() == 0
        assert DataAsset.objects.filter(id=a2).count() == 1

    released = client.post(f'/api/v1/retention/holds/{hold_id}/release', HTTP_HOST=host)
    assert released.status_code == 200
    assert released.json()['active'] is False


@pytest.mark.django_db(transaction=True)
def test_retention_is_tenant_scoped():
    host_a, _, host_b, _ = _create_tenants()
    client = Client()
    asset_a = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    ).json()['id']

    rule = client.post(
        '/api/v1/retention/rules',
        data=json.dumps({'scope': {'asset_types': ['table']}, 'action': 'archive', 'retention_period': 'P0D'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert rule.status_code == 201
    rule_id = rule.json()['id']

    assert len(client.get('/api/v1/retention/rules', HTTP_HOST=host_a).json()['items']) == 1
    assert client.get('/api/v1/retention/rules', HTTP_HOST=host_b).json()['items'] == []

    not_found = client.post(
        '/api/v1/retention/runs',
        data=json.dumps({'rule_id': rule_id, 'mode': 'execute'}),
        content_type='application/json',
        HTTP_HOST=host_b,
    )
    assert not_found.status_code == 404

    _ = asset_a


@pytest.mark.django_db(transaction=True)
def test_retention_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _, _, _ = _create_tenants()
    client = Client()
    asset = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    ).json()['id']

    denied_rule = client.post(
        '/api/v1/retention/rules',
        data=json.dumps({'scope': {}, 'action': 'delete', 'retention_period': 'P0D'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_rule.status_code == 403

    allowed_rule = client.post(
        '/api/v1/retention/rules',
        data=json.dumps({'scope': {}, 'action': 'delete', 'retention_period': 'P0D'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='policy.admin',
    )
    assert allowed_rule.status_code == 201
    rule_id = allowed_rule.json()['id']

    denied_run = client.post(
        '/api/v1/retention/runs',
        data=json.dumps({'rule_id': rule_id, 'mode': 'execute'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_run.status_code == 403

    allowed_run = client.post(
        '/api/v1/retention/runs',
        data=json.dumps({'rule_id': rule_id, 'mode': 'dry_run'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed_run.status_code == 201

    denied_read = client.get('/api/v1/retention/rules', HTTP_HOST=host)
    assert denied_read.status_code == 403
    allowed_read = client.get('/api/v1/retention/rules', HTTP_HOST=host, HTTP_X_USER_ROLES='catalog.reader')
    assert allowed_read.status_code == 200

    denied_hold = client.post(
        '/api/v1/retention/holds',
        data=json.dumps({'asset_id': asset}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_hold.status_code == 403
