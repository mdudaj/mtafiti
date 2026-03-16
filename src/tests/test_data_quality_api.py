import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


@pytest.mark.django_db(transaction=True)
def test_quality_rule_create_evaluate_and_results():
    host = f"tenant-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()

    client = Client()
    created_asset = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created_asset.status_code == 201
    asset_id = created_asset.json()['id']

    created_rule = client.post(
        '/api/v1/quality/rules',
        data=json.dumps(
            {'asset_id': asset_id, 'rule_type': 'freshness', 'params': {'max_age_minutes': 0, 'force_status': 'warn'}, 'severity': 'warning'}
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created_rule.status_code == 201
    rule_id = created_rule.json()['id']

    listed_rules = client.get('/api/v1/quality/rules', HTTP_HOST=host)
    assert listed_rules.status_code == 200
    assert len(listed_rules.json()['items']) == 1

    evaluated = client.post(f'/api/v1/quality/rules/{rule_id}/evaluate', HTTP_HOST=host)
    assert evaluated.status_code == 200
    assert evaluated.json()['status'] == 'warn'

    listed_results = client.get(f'/api/v1/quality/results?rule_id={rule_id}', HTTP_HOST=host)
    assert listed_results.status_code == 200
    assert len(listed_results.json()['items']) == 1
    assert listed_results.json()['items'][0]['status'] == 'warn'


@pytest.mark.django_db(transaction=True)
def test_quality_endpoints_are_tenant_scoped():
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
    created_asset = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created_asset.status_code == 201

    created_rule = client.post(
        '/api/v1/quality/rules',
        data=json.dumps({'asset_id': created_asset.json()['id'], 'rule_type': 'freshness', 'params': {'force_status': 'pass'}}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created_rule.status_code == 201
    rule_id = created_rule.json()['id']

    assert client.get('/api/v1/quality/rules', HTTP_HOST=host_a).json()['items']
    assert client.get('/api/v1/quality/rules', HTTP_HOST=host_b).json()['items'] == []

    not_found_other_tenant = client.post(f'/api/v1/quality/rules/{rule_id}/evaluate', HTTP_HOST=host_b)
    assert not_found_other_tenant.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_quality_endpoints_enforce_roles_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host = f"tenant-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()

    client = Client()
    created_asset = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created_asset.status_code == 201

    denied_create = client.post(
        '/api/v1/quality/rules',
        data=json.dumps({'asset_id': created_asset.json()['id'], 'rule_type': 'freshness'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert denied_create.status_code == 403

    allowed_create = client.post(
        '/api/v1/quality/rules',
        data=json.dumps({'asset_id': created_asset.json()['id'], 'rule_type': 'freshness'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert allowed_create.status_code == 201
    rule_id = allowed_create.json()['id']

    denied_read = client.get('/api/v1/quality/rules', HTTP_HOST=host)
    assert denied_read.status_code == 403

    allowed_read = client.get('/api/v1/quality/rules', HTTP_HOST=host, HTTP_X_USER_ROLES='catalog.reader')
    assert allowed_read.status_code == 200

    denied_eval = client.post(f'/api/v1/quality/rules/{rule_id}/evaluate', HTTP_HOST=host, HTTP_X_USER_ROLES='catalog.reader')
    assert denied_eval.status_code == 403
