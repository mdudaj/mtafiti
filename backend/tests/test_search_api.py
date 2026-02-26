import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


@pytest.mark.django_db(transaction=True)
def test_search_assets_is_tenant_scoped():
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
    created = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.sales.orders', 'asset_type': 'table', 'description': 'Orders'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201

    hit = client.get('/api/v1/search/assets?q=orders', HTTP_HOST=host_a)
    assert hit.status_code == 200
    assert hit.json()['count'] == 1

    miss = client.get('/api/v1/search/assets?q=orders', HTTP_HOST=host_b)
    assert miss.status_code == 200
    assert miss.json()['count'] == 0


@pytest.mark.django_db(transaction=True)
def test_search_assets_supports_catalog_fields_and_pagination():
    host = f"tenant-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()

    client = Client()
    assets = [
        {'qualified_name': 'db.customer_dim', 'asset_type': 'table', 'description': 'Customer profile', 'owner': 'data-platform'},
        {'qualified_name': 'db.sales_fact', 'asset_type': 'table', 'description': 'Sales facts', 'owner': 'analytics'},
        {'qualified_name': 'db.daily_report', 'asset_type': 'report', 'description': 'Daily summary', 'owner': 'analytics'},
    ]
    for a in assets:
        resp = client.post('/api/v1/assets', data=json.dumps(a), content_type='application/json', HTTP_HOST=host)
        assert resp.status_code == 201

    by_text = client.get('/api/v1/search/assets?q=customer', HTTP_HOST=host)
    assert by_text.status_code == 200
    assert by_text.json()['count'] == 1

    by_type = client.get('/api/v1/search/assets?q=report', HTTP_HOST=host)
    assert by_type.status_code == 200
    assert by_type.json()['count'] == 1

    by_owner = client.get('/api/v1/search/assets?q=analytics', HTTP_HOST=host)
    assert by_owner.status_code == 200
    assert by_owner.json()['count'] == 2

    paged = client.get('/api/v1/search/assets?q=db&limit=1&offset=1', HTTP_HOST=host)
    assert paged.status_code == 200
    assert paged.json()['count'] == 3
    assert len(paged.json()['results']) == 1


@pytest.mark.django_db(transaction=True)
def test_search_assets_enforces_reader_role_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host = f"tenant-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()

    client = Client()
    created = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201

    denied = client.get('/api/v1/search/assets?q=orders', HTTP_HOST=host)
    assert denied.status_code == 403

    allowed = client.get('/api/v1/search/assets?q=orders', HTTP_HOST=host, HTTP_X_USER_ROLES='catalog.reader')
    assert allowed.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_search_assets_validates_query_and_paging_params():
    host = f"tenant-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()

    client = Client()
    missing_q = client.get('/api/v1/search/assets', HTTP_HOST=host)
    assert missing_q.status_code == 400

    bad_paging = client.get('/api/v1/search/assets?q=a&limit=x', HTTP_HOST=host)
    assert bad_paging.status_code == 400
