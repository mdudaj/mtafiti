import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from core.models import Project
from tenants.models import Domain, Tenant, TenantServiceRoute


@pytest.mark.django_db(transaction=True)
def test_requests_without_tenant_are_rejected():
    client = Client()
    resp = client.get('/', HTTP_HOST='unknown.example')
    assert resp.status_code == 404
    assert resp.json() == {'error': 'tenant_not_found'}
    assert resp.headers.get('X-Correlation-Id')
    assert uuid.UUID(resp.headers['X-Correlation-Id'])


@pytest.mark.django_db(transaction=True)
def test_schema_per_tenant_isolated_data_and_routing():
    host_a = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    host_b = f"tenantb-{uuid.uuid4().hex[:6]}.example"
    tenant_a = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f'Tenant A {uuid.uuid4().hex[:6]}')
    tenant_a.save()
    Domain(domain=host_a, tenant=tenant_a, is_primary=True).save()

    tenant_b = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f'Tenant B {uuid.uuid4().hex[:6]}')
    tenant_b.save()
    Domain(domain=host_b, tenant=tenant_b, is_primary=True).save()

    with schema_context(tenant_a.schema_name):
        Project.objects.create(name='A')
        assert Project.objects.count() == 1

    with schema_context(tenant_b.schema_name):
        Project.objects.create(name='B')
        assert Project.objects.count() == 1

    with schema_context(tenant_a.schema_name):
        assert Project.objects.filter(name='B').count() == 0

    client = Client()
    resp = client.get('/', HTTP_HOST=host_a)
    assert resp.status_code == 200
    assert resp.json()['schema'] == tenant_a.schema_name


@pytest.mark.django_db(transaction=True)
def test_service_route_hostname_resolves_tenant():
    with schema_context('public'):
        tenant_slug = f"tenantsvc-{uuid.uuid4().hex[:6]}"
        base_domain = f"platform-{uuid.uuid4().hex[:6]}.example"
        domain = f"{tenant_slug}.example"
        tenant = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f'Tenant Service {uuid.uuid4().hex[:6]}',
        )
        tenant.save()
        Domain(domain=domain, tenant=tenant, is_primary=True).save()
        TenantServiceRoute.objects.create(
            tenant=tenant,
            service_key='printing',
            tenant_slug=tenant_slug,
            base_domain=base_domain,
            workspace_path='/app',
            is_enabled=True,
        )

    client = Client()
    routed = client.get('/', HTTP_HOST=f'printing.{tenant_slug}.{base_domain}')
    assert routed.status_code == 200
    assert routed.json()['schema'] == tenant.schema_name


@pytest.mark.django_db(transaction=True)
def test_service_route_hostname_renders_user_portal_for_tenant():
    with schema_context('public'):
        tenant_slug = f"tenantlab-{uuid.uuid4().hex[:6]}"
        primary_domain = f"{tenant_slug}.example"
        tenant = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f'Tenant Lab Portal {uuid.uuid4().hex[:6]}',
        )
        tenant.save()
        Domain(domain=primary_domain, tenant=tenant, is_primary=True).save()
        TenantServiceRoute.objects.create(
            tenant=tenant,
            service_key='lab',
            tenant_slug=tenant_slug,
            base_domain='edmp.co.tz',
            workspace_path='/app',
            is_enabled=True,
        )

    client = Client()
    created = client.post(
        '/api/v1/printing/templates',
        data='{"name":"E2E Lab Template","template_ref":"lab/e2e","output_format":"pdf","content":"QR [[content]]"}',
        content_type='application/json',
        HTTP_HOST=primary_domain,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201

    page = client.get(
        '/app',
        HTTP_HOST=f'lab.{tenant_slug}.edmp.co.tz',
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert page.status_code == 200
    assert b'User Workspace' in page.content
    assert b'E2E Lab Template' in page.content


@pytest.mark.django_db(transaction=True)
def test_tenant_root_hostname_resolves_via_service_route_slug():
    with schema_context('public'):
        tenant_slug = f"tenantroot-{uuid.uuid4().hex[:6]}"
        tenant = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f'Tenant Root {uuid.uuid4().hex[:6]}',
        )
        tenant.save()
        Domain(domain=f'{tenant_slug}.example', tenant=tenant, is_primary=True).save()
        TenantServiceRoute.objects.create(
            tenant=tenant,
            service_key='lab',
            tenant_slug=tenant_slug,
            base_domain='edmp.co.tz',
            workspace_path='/app',
            is_enabled=True,
        )

    client = Client()
    routed = client.get('/', HTTP_HOST=f'{tenant_slug}.edmp.co.tz')
    assert routed.status_code == 200
    assert routed.json()['schema'] == tenant.schema_name


@pytest.mark.django_db(transaction=True)
def test_tenant_first_service_hostname_resolves_tenant():
    with schema_context('public'):
        tenant_slug = f"tenantfirst-{uuid.uuid4().hex[:6]}"
        tenant = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f'Tenant First {uuid.uuid4().hex[:6]}',
        )
        tenant.save()
        Domain(domain=f'{tenant_slug}.example', tenant=tenant, is_primary=True).save()
        TenantServiceRoute.objects.create(
            tenant=tenant,
            service_key='edcs',
            tenant_slug=tenant_slug,
            base_domain='edmp.co.tz',
            workspace_path='/app',
            is_enabled=True,
        )

    client = Client()
    routed = client.get('/', HTTP_HOST=f'{tenant_slug}.edcs.edmp.co.tz')
    assert routed.status_code == 200
    assert routed.json()['schema'] == tenant.schema_name
