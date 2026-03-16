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
def test_collaboration_document_lifecycle():
    host, _ = _create_tenants()
    client = Client()

    created = client.post(
        '/api/v1/collaboration/documents',
        data=json.dumps(
            {
                'title': 'Policy Draft',
                'object_key': 'tenant-a/docs/policy-draft.docx',
                'content_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'owner': 'owner@example.com',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    document_id = created.json()['id']

    listed = client.get('/api/v1/collaboration/documents', HTTP_HOST=host)
    assert listed.status_code == 200
    assert len(listed.json()['items']) == 1

    view_session = client.post(
        f'/api/v1/collaboration/documents/{document_id}/session',
        data=json.dumps({'mode': 'view'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert view_session.status_code == 200
    assert view_session.json()['mode'] == 'view'

    edit_session = client.post(
        f'/api/v1/collaboration/documents/{document_id}/session',
        data=json.dumps({'mode': 'edit'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert edit_session.status_code == 200
    assert edit_session.json()['mode'] == 'edit'

    v1 = client.post(
        f'/api/v1/collaboration/documents/{document_id}/versions',
        data=json.dumps(
            {
                'object_key': 'tenant-a/docs/policy-draft-v1.docx',
                'summary': 'Initial edits',
                'editor': 'editor@example.com',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert v1.status_code == 201
    assert v1.json()['version'] == 1

    detail = client.get(
        f'/api/v1/collaboration/documents/{document_id}',
        HTTP_HOST=host,
    )
    assert detail.status_code == 200
    assert detail.json()['latest_version'] == 1

    updated = client.patch(
        f'/api/v1/collaboration/documents/{document_id}',
        data=json.dumps({'title': 'Policy Draft v2'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert updated.status_code == 200
    assert updated.json()['title'] == 'Policy Draft v2'

    versions = client.get(
        f'/api/v1/collaboration/documents/{document_id}/versions',
        HTTP_HOST=host,
    )
    assert versions.status_code == 200
    assert len(versions.json()['items']) == 1


@pytest.mark.django_db(transaction=True)
def test_collaboration_is_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()

    created = client.post(
        '/api/v1/collaboration/documents',
        data=json.dumps(
            {
                'title': 'Policy Draft',
                'object_key': 'tenant-a/docs/policy-draft.docx',
            }
        ),
        content_type='application/json',
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    document_id = created.json()['id']

    assert len(client.get('/api/v1/collaboration/documents', HTTP_HOST=host_a).json()['items']) == 1
    assert client.get('/api/v1/collaboration/documents', HTTP_HOST=host_b).json()['items'] == []
    assert client.get(f'/api/v1/collaboration/documents/{document_id}', HTTP_HOST=host_b).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_collaboration_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host, _ = _create_tenants()
    client = Client()

    denied_create = client.post(
        '/api/v1/collaboration/documents',
        data=json.dumps({'title': 'Doc', 'object_key': 'k'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert denied_create.status_code == 403

    created = client.post(
        '/api/v1/collaboration/documents',
        data=json.dumps({'title': 'Doc', 'object_key': 'k'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created.status_code == 201
    document_id = created.json()['id']

    allowed_view = client.post(
        f'/api/v1/collaboration/documents/{document_id}/session',
        data=json.dumps({'mode': 'view'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert allowed_view.status_code == 200

    denied_edit = client.post(
        f'/api/v1/collaboration/documents/{document_id}/session',
        data=json.dumps({'mode': 'edit'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert denied_edit.status_code == 403

    allowed_edit = client.post(
        f'/api/v1/collaboration/documents/{document_id}/session',
        data=json.dumps({'mode': 'edit'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert allowed_edit.status_code == 200

    denied_versions = client.post(
        f'/api/v1/collaboration/documents/{document_id}/versions',
        data=json.dumps({'object_key': 'v1'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.reader',
    )
    assert denied_versions.status_code == 403

    allowed_versions = client.post(
        f'/api/v1/collaboration/documents/{document_id}/versions',
        data=json.dumps({'object_key': 'v1'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed_versions.status_code == 201
