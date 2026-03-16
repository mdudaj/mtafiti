import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


def _create_tenant_host() -> str:
    host = f"tenant-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(schema_name=f't_{uuid.uuid4().hex[:8]}', name=f"Tenant {uuid.uuid4().hex[:6]}")
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()
    return host


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


@pytest.mark.django_db(transaction=True)
def test_ui_model_select_projects_is_tenant_scoped_and_searchable():
    host_a = _create_tenant_host()
    host_b = _create_tenant_host()
    client = Client()

    created = client.post(
        '/api/v1/projects',
        data=json.dumps({'name': 'Dar Research Hub', 'code': 'DAR-01', 'institution_ref': 'MUHAS'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201

    hit = client.get(
        '/api/v1/ui/model-select-options?source=projects&q=Dar',
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert hit.status_code == 200
    assert hit.json()['count'] == 1
    assert hit.json()['results'][0]['label'] == 'Dar Research Hub'
    assert hit.json()['results'][0]['description'] == 'DAR-01 · MUHAS'

    miss = client.get(
        '/api/v1/ui/model-select-options?source=projects&q=Dar',
        HTTP_HOST=host_b,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert miss.status_code == 200
    assert miss.json()['count'] == 0


@pytest.mark.django_db(transaction=True)
def test_ui_model_select_projects_validates_source_and_roles(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host = _create_tenant_host()
    client = Client()

    client.post(
        '/api/v1/projects',
        data=json.dumps({'name': 'Mtwara Field Study', 'code': 'MTW-02'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )

    denied = client.get('/api/v1/ui/model-select-options?source=projects&q=mtw', HTTP_HOST=host)
    assert denied.status_code == 403

    bad_source = client.get(
        '/api/v1/ui/model-select-options?source=unknown',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert bad_source.status_code == 400

    bad_paging = client.get(
        '/api/v1/ui/model-select-options?source=projects&limit=x',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert bad_paging.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_ui_model_select_print_templates_and_gateways_are_searchable():
    host = _create_tenant_host()
    client = Client()

    template = client.post(
        '/api/v1/printing/templates',
        data=json.dumps(
            {
                'name': 'Zebra Search Template',
                'template_ref': 'zebra/search-test',
                'output_format': 'zpl',
                'content': '^XA^XZ',
                'sample_payload': {'content': 'T-001'},
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert template.status_code == 201

    gateway = client.post(
        '/api/v1/printing/gateways',
        data=json.dumps(
            {
                'gateway_ref': 'lab-zebra-01',
                'display_name': 'Lab Zebra Printer',
                'site_ref': 'Dar Lab',
                'status': 'online',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert gateway.status_code == 201

    template_search = client.get(
        '/api/v1/ui/model-select-options?source=print_templates&q=search',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert template_search.status_code == 200
    assert template_search.json()['count'] == 1
    assert template_search.json()['results'][0]['label'] == 'Zebra Search Template'
    assert 'zebra/search-test' in template_search.json()['results'][0]['description']

    gateway_search = client.get(
        '/api/v1/ui/model-select-options?source=print_gateways&q=lab',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert gateway_search.status_code == 200
    assert gateway_search.json()['count'] == 1
    assert gateway_search.json()['results'][0]['label'] == 'Lab Zebra Printer'
    assert gateway_search.json()['results'][0]['value'] == 'lab-zebra-01'


@pytest.mark.django_db(transaction=True)
def test_ui_model_select_assets_are_tenant_scoped_and_return_metadata():
    host_a = _create_tenant_host()
    host_b = _create_tenant_host()
    client = Client()

    created = client.post(
        '/api/v1/assets',
        data=json.dumps(
            {
                'qualified_name': 'lake.vitals.observations',
                'display_name': 'Vitals Observations',
                'asset_type': 'table',
                'description': 'Vitals fact table',
                'owner': 'clinical-platform',
                'tags': ['clinical'],
            }
        ),
        content_type='application/json',
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201

    hit = client.get(
        '/api/v1/ui/model-select-options?source=assets&q=clinical',
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert hit.status_code == 200
    assert hit.json()['count'] == 1
    assert hit.json()['results'][0]['label'] == 'Vitals Observations'
    assert hit.json()['results'][0]['description'] == (
        'lake.vitals.observations · table · clinical-platform'
    )
    assert hit.json()['results'][0]['meta']['qualified_name'] == 'lake.vitals.observations'

    miss = client.get(
        '/api/v1/ui/model-select-options?source=assets&q=clinical',
        HTTP_HOST=host_b,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert miss.status_code == 200
    assert miss.json()['count'] == 0


@pytest.mark.django_db(transaction=True)
def test_ui_model_select_workflow_definitions_are_searchable():
    host = _create_tenant_host()
    client = Client()

    resp_a = client.post(
        '/api/v1/workflows/definitions',
        data=json.dumps(
            {
                'name': 'Retention Review',
                'description': 'Review retention policy changes',
                'domain_ref': 'governance',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert resp_a.status_code == 201

    resp_b = client.post(
        '/api/v1/workflows/definitions',
        data=json.dumps(
            {
                'name': 'Ingestion Approval',
                'description': 'Approve ingestion run onboarding',
                'domain_ref': 'operations',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert resp_b.status_code == 201

    search = client.get(
        '/api/v1/ui/model-select-options?source=workflow_definitions&q=governance&limit=1',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert search.status_code == 200
    assert search.json()['count'] == 1
    assert len(search.json()['results']) == 1
    assert search.json()['results'][0]['label'] == 'Retention Review'
    assert search.json()['results'][0]['meta']['domain_ref'] == 'governance'
