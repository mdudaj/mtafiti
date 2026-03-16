import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


def _create_tenant_host() -> str:
    host = f'tenant-{uuid.uuid4().hex[:6]}.example'
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()
    return host


@pytest.mark.django_db(transaction=True)
def test_assets_pagination_defaults_and_caps():
    host = _create_tenant_host()
    client = Client()
    for idx in range(120):
        created = client.post(
            '/api/v1/assets',
            data=json.dumps({'qualified_name': f'db.table_{idx}', 'asset_type': 'table'}),
            content_type='application/json',
            HTTP_HOST=host,
        )
        assert created.status_code == 201

    default_page = client.get('/api/v1/assets', HTTP_HOST=host)
    assert default_page.status_code == 200
    assert default_page.json()['page'] == 1
    assert default_page.json()['page_size'] == 50
    assert default_page.json()['total'] == 120
    assert len(default_page.json()['items']) == 50

    second_page = client.get('/api/v1/assets?page=2&page_size=50', HTTP_HOST=host)
    assert second_page.status_code == 200
    assert second_page.json()['page'] == 2
    assert len(second_page.json()['items']) == 50

    capped = client.get('/api/v1/assets?page=1&page_size=500', HTTP_HOST=host)
    assert capped.status_code == 200
    assert capped.json()['page_size'] == 100
    assert len(capped.json()['items']) == 100


@pytest.mark.django_db(transaction=True)
def test_ingestions_pagination_and_legacy_limit_offset():
    host = _create_tenant_host()
    client = Client()
    for _ in range(25):
        created = client.post(
            '/api/v1/ingestions',
            data=json.dumps({'connector': 'dbt', 'source': {}}),
            content_type='application/json',
            HTTP_HOST=host,
        )
        assert created.status_code == 201

    page = client.get('/api/v1/ingestions?page=2&page_size=10', HTTP_HOST=host)
    assert page.status_code == 200
    assert page.json()['page'] == 2
    assert page.json()['page_size'] == 10
    assert page.json()['total'] == 25
    assert len(page.json()['items']) == 10

    legacy = client.get('/api/v1/ingestions?limit=5&offset=10', HTTP_HOST=host)
    assert legacy.status_code == 200
    assert legacy.json()['page_size'] == 5
    assert legacy.json()['page'] == 3
    assert len(legacy.json()['items']) == 5
