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
def test_notebook_workspace_session_execution_lifecycle():
    host, _ = _create_tenants()
    client = Client()

    workspace = client.post(
        '/api/v1/notebooks/workspaces',
        data=json.dumps(
            {
                'name': 'analysis-ws',
                'owner': 'analyst@example.com',
                'image': 'jupyter/scipy-notebook:latest',
                'cpu_limit': '2',
                'memory_limit': '4Gi',
                'storage_mounts': ['tenant-a/data', 'tenant-a/notebooks'],
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert workspace.status_code == 201
    workspace_id = workspace.json()['id']

    started = client.post(
        f'/api/v1/notebooks/workspaces/{workspace_id}/sessions',
        data=json.dumps({'user_id': 'analyst@example.com', 'pod_name': 'nb-pod-1'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert started.status_code == 201
    session_id = started.json()['id']
    assert started.json()['status'] == 'started'

    listed_sessions = client.get(
        f'/api/v1/notebooks/sessions?workspace_id={workspace_id}',
        HTTP_HOST=host,
    )
    assert listed_sessions.status_code == 200
    assert len(listed_sessions.json()['items']) == 1

    execution = client.post(
        f'/api/v1/notebooks/sessions/{session_id}/executions',
        data=json.dumps({'cell_ref': 'cell-1', 'metadata': {'kernel': 'python3'}}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert execution.status_code == 201
    execution_id = execution.json()['id']
    assert execution.json()['status'] == 'requested'

    completed = client.post(
        f'/api/v1/notebooks/executions/{execution_id}/complete',
        data=json.dumps({'status': 'completed'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert completed.status_code == 200
    assert completed.json()['status'] == 'completed'

    terminated = client.post(
        f'/api/v1/notebooks/sessions/{session_id}/terminate',
        data=json.dumps({'reason': 'terminated'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert terminated.status_code == 200
    assert terminated.json()['status'] == 'terminated'


@pytest.mark.django_db(transaction=True)
def test_notebooks_are_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()

    workspace = client.post(
        '/api/v1/notebooks/workspaces',
        data=json.dumps({'name': 'analysis-ws'}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert workspace.status_code == 201
    workspace_id = workspace.json()['id']

    session = client.post(
        f'/api/v1/notebooks/workspaces/{workspace_id}/sessions',
        data=json.dumps({}),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert session.status_code == 201
    session_id = session.json()['id']

    assert len(client.get('/api/v1/notebooks/workspaces', HTTP_HOST=host_a).json()['items']) == 1
    assert client.get('/api/v1/notebooks/workspaces', HTTP_HOST=host_b).json()['items'] == []
    assert (
        client.post(
            f'/api/v1/notebooks/sessions/{session_id}/terminate',
            data=json.dumps({'reason': 'terminated'}),
            content_type='application/json',
            HTTP_HOST=host_b,
        ).status_code
        == 404
    )


@pytest.mark.django_db(transaction=True)
def test_notebooks_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _ = _create_tenants()
    client = Client()

    denied_workspace = client.post(
        '/api/v1/notebooks/workspaces',
        data=json.dumps({'name': 'analysis-ws'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert denied_workspace.status_code == 403

    workspace = client.post(
        '/api/v1/notebooks/workspaces',
        data=json.dumps({'name': 'analysis-ws'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert workspace.status_code == 201
    workspace_id = workspace.json()['id']

    denied_start = client.post(
        f'/api/v1/notebooks/workspaces/{workspace_id}/sessions',
        data=json.dumps({}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert denied_start.status_code == 403

    started = client.post(
        f'/api/v1/notebooks/workspaces/{workspace_id}/sessions',
        data=json.dumps({}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert started.status_code == 201
    session_id = started.json()['id']

    denied_exec = client.post(
        f'/api/v1/notebooks/sessions/{session_id}/executions',
        data=json.dumps({}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert denied_exec.status_code == 403

    allowed_exec = client.post(
        f'/api/v1/notebooks/sessions/{session_id}/executions',
        data=json.dumps({}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert allowed_exec.status_code == 201
    execution_id = allowed_exec.json()['id']

    denied_complete = client.post(
        f'/api/v1/notebooks/executions/{execution_id}/complete',
        data=json.dumps({'status': 'completed'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert denied_complete.status_code == 403

    allowed_complete = client.post(
        f'/api/v1/notebooks/executions/{execution_id}/complete',
        data=json.dumps({'status': 'completed'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed_complete.status_code == 200
