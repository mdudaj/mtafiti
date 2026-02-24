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
def test_role_enforcement_is_opt_in():
    host = _create_tenant_host()
    client = Client()
    created = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.table', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert created.status_code == 201


@pytest.mark.django_db(transaction=True)
def test_tenant_create_enforces_tenant_admin_role(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')

    client = Client()
    denied = client.post(
        '/api/v1/tenants',
        data=json.dumps({'name': 'Tenant A', 'domain': f"tenant-{uuid.uuid4().hex[:6]}.example"}),
        content_type='application/json',
        HTTP_HOST='control.example',
    )
    assert denied.status_code == 403

    allowed = client.post(
        '/api/v1/tenants',
        data=json.dumps({'name': 'Tenant B', 'domain': f"tenant-{uuid.uuid4().hex[:6]}.example"}),
        content_type='application/json',
        HTTP_HOST='control.example',
        HTTP_X_USER_ROLES='tenant.admin',
    )
    assert allowed.status_code == 201


@pytest.mark.django_db(transaction=True)
def test_catalog_mutations_enforce_catalog_editor_role(monkeypatch):
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    host = _create_tenant_host()
    client = Client()

    denied_create = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.a', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert denied_create.status_code == 403

    created_a = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.a', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created_a.status_code == 201

    created_b = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.b', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert created_b.status_code == 201

    denied_update = client.put(
        f"/api/v1/assets/{created_a.json()['id']}",
        data=json.dumps({'display_name': 'Table A'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert denied_update.status_code == 403

    allowed_update = client.put(
        f"/api/v1/assets/{created_a.json()['id']}",
        data=json.dumps({'display_name': 'Table A'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert allowed_update.status_code == 200

    denied_ingestion = client.post(
        '/api/v1/ingestions',
        data=json.dumps({'connector': 'dbt', 'source': {'project': 'x'}}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert denied_ingestion.status_code == 403

    allowed_ingestion = client.post(
        '/api/v1/ingestions',
        data=json.dumps({'connector': 'dbt', 'source': {'project': 'x'}}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert allowed_ingestion.status_code == 201

    denied_lineage = client.post(
        '/api/v1/lineage/edges',
        data=json.dumps(
            {'items': [{'from_asset_id': created_a.json()['id'], 'to_asset_id': created_b.json()['id'], 'edge_type': 'reads_from'}]}
        ),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert denied_lineage.status_code == 403

    allowed_lineage = client.post(
        '/api/v1/lineage/edges',
        data=json.dumps(
            {'items': [{'from_asset_id': created_a.json()['id'], 'to_asset_id': created_b.json()['id'], 'edge_type': 'reads_from'}]}
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
    )
    assert allowed_lineage.status_code == 200
