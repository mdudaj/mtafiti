import json
import uuid

import pytest
from django.test import Client


@pytest.mark.django_db(transaction=True)
def test_lims_service_route_exposes_summary_and_html_shell():
    client = Client()
    control_host = 'control.example'
    created_tenant = client.post(
        '/api/v1/tenants',
        data=json.dumps(
            {
                'name': f'Tenant {uuid.uuid4().hex[:6]}',
                'domain': f"tenant-{uuid.uuid4().hex[:6]}.example",
            }
        ),
        content_type='application/json',
        HTTP_HOST=control_host,
    )
    assert created_tenant.status_code == 201
    tenant_id = created_tenant.json()['id']

    created_route = client.post(
        '/api/v1/tenants/services',
        data=json.dumps(
            {
                'tenant_id': tenant_id,
                'service_key': 'lims',
                'tenant_slug': 'tenant-alpha',
                'base_domain': 'mtafiti.apps.nimr.or.tz',
            }
        ),
        content_type='application/json',
        HTTP_HOST=control_host,
    )
    assert created_route.status_code == 201
    host = created_route.json()['domain']

    summary = client.get(
        '/api/v1/lims/summary',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert summary.status_code == 200
    assert summary.json()['service_key'] == 'lims'
    assert summary.json()['tenant_schema'].startswith('t_')

    page = client.get('/lims/', HTTP_HOST=host, HTTP_X_USER_ROLES='tenant.admin')
    assert page.status_code == 200
    assert b'Laboratory operations workspace' in page.content


@pytest.mark.django_db(transaction=True)
def test_lims_service_route_enforces_roles_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    client = Client()
    control_host = 'control.example'
    created_tenant = client.post(
        '/api/v1/tenants',
        data=json.dumps(
            {
                'name': f'Tenant {uuid.uuid4().hex[:6]}',
                'domain': f"tenant-{uuid.uuid4().hex[:6]}.example",
            }
        ),
        content_type='application/json',
        HTTP_HOST=control_host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert created_tenant.status_code == 201
    tenant_id = created_tenant.json()['id']
    created_route = client.post(
        '/api/v1/tenants/services',
        data=json.dumps(
            {
                'tenant_id': tenant_id,
                'service_key': 'lims',
                'tenant_slug': 'tenant-beta',
                'base_domain': 'mtafiti.apps.nimr.or.tz',
            }
        ),
        content_type='application/json',
        HTTP_HOST=control_host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert created_route.status_code == 201
    host = created_route.json()['domain']

    denied = client.get('/api/v1/lims/summary', HTTP_HOST=host)
    assert denied.status_code == 403

    allowed = client.get(
        '/api/v1/lims/summary',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert allowed.status_code == 200
