import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from core.models import Project
from tenants.models import Domain, Tenant


@pytest.mark.django_db(transaction=True)
def test_requests_without_tenant_are_rejected():
    client = Client()
    resp = client.get('/', HTTP_HOST='unknown.example')
    assert resp.status_code == 404
    assert resp.json() == {'error': 'tenant_not_found'}
    assert resp.headers.get('X-Correlation-Id')
    uuid.UUID(resp.headers['X-Correlation-Id'])


@pytest.mark.django_db(transaction=True)
def test_schema_per_tenant_isolated_data_and_routing():
    tenant_a = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name='Tenant A')
    tenant_a.save()
    Domain(domain='tenanta.example', tenant=tenant_a, is_primary=True).save()

    tenant_b = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name='Tenant B')
    tenant_b.save()
    Domain(domain='tenantb.example', tenant=tenant_b, is_primary=True).save()

    with schema_context(tenant_a.schema_name):
        Project.objects.create(name='A')
        assert Project.objects.count() == 1

    with schema_context(tenant_b.schema_name):
        Project.objects.create(name='B')
        assert Project.objects.count() == 1

    with schema_context(tenant_a.schema_name):
        assert Project.objects.filter(name='B').count() == 0

    client = Client()
    resp = client.get('/', HTTP_HOST='tenanta.example')
    assert resp.status_code == 200
    assert resp.json()['schema'] == tenant_a.schema_name
