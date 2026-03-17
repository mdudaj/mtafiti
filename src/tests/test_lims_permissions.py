import json
import uuid

import pytest
from django.test import Client

from lims.permissions import (
    guardian_permission_name,
    has_lims_permission,
    permission_summary_for_roles,
    permissions_for_roles,
    viewflow_task_permission_name,
)


def _create_lims_host(client: Client, route_slug: str) -> str:
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
                'tenant_slug': route_slug,
                'base_domain': 'mtafiti.apps.nimr.or.tz',
            }
        ),
        content_type='application/json',
        HTTP_HOST=control_host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert created_route.status_code == 201
    return created_route.json()['domain']


def test_lims_permission_model_exposes_guardian_and_viewflow_names():
    assert guardian_permission_name('lims.reference.manage') == 'lims.manage_reference_record'
    assert viewflow_task_permission_name('approve') == 'lims.approve_workflow_task'
    assert viewflow_task_permission_name('assign') == 'lims.assign_workflow_task'


def test_lims_permission_model_supports_module_and_legacy_roles():
    manager_permissions = permissions_for_roles({'lims.manager'})
    assert 'lims.workflow_task.assign' in manager_permissions
    assert 'lims.reference.manage' in manager_permissions
    assert 'lims.workflow_task.approve' not in manager_permissions

    legacy_permissions = permissions_for_roles({'catalog.editor', 'policy.admin'})
    assert 'lims.workflow_task.execute' in legacy_permissions
    assert 'lims.workflow_task.approve' in legacy_permissions
    assert has_lims_permission({'tenant.admin'}, 'lims.artifact.manage')


def test_lims_permission_summary_reports_effective_permissions():
    summary = permission_summary_for_roles({'lims.qa', 'catalog.reader'})
    assert 'lims.artifact.manage' in summary['effective_permissions']
    assert summary['viewflow_task_permissions']['approve'] == 'lims.approve_workflow_task'
    assert any(item['role'] == 'lims.qa' for item in summary['role_bundles'])
    assert any(item['role'] == 'catalog.reader' for item in summary['legacy_role_compatibility'])


@pytest.mark.django_db(transaction=True)
def test_lims_permissions_endpoint_requires_lims_dashboard_access(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    client = Client()
    host = _create_lims_host(client, 'tenant-gamma')

    denied = client.get('/api/v1/lims/permissions', HTTP_HOST=host)
    assert denied.status_code == 403

    allowed = client.get(
        '/api/v1/lims/permissions',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='lims.manager',
    )
    assert allowed.status_code == 200
    payload = allowed.json()
    assert 'lims.workflow_task.assign' in payload['effective_permissions']
    assert payload['viewflow_task_permissions']['execute'] == 'lims.execute_workflow_task'


@pytest.mark.django_db(transaction=True)
def test_lims_dashboard_accepts_new_lims_roles(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    client = Client()
    host = _create_lims_host(client, 'tenant-delta')

    allowed = client.get(
        '/api/v1/lims/summary',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='lims.operator',
    )
    assert allowed.status_code == 200
