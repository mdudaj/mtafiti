import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


def _create_tenants():
    host_a = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    host_b = f"tenantb-{uuid.uuid4().hex[:6]}.example"
    with schema_context("public"):
        tenant_a = Tenant(
            schema_name=f"t_{uuid.uuid4().hex[:8]}",
            name=f"Tenant A {uuid.uuid4().hex[:6]}",
        )
        tenant_a.save()
        Domain(domain=host_a, tenant=tenant_a, is_primary=True).save()
        tenant_b = Tenant(
            schema_name=f"t_{uuid.uuid4().hex[:8]}",
            name=f"Tenant B {uuid.uuid4().hex[:6]}",
        )
        tenant_b.save()
        Domain(domain=host_b, tenant=tenant_b, is_primary=True).save()
    return host_a, host_b


@pytest.mark.django_db(transaction=True)
def test_asset_version_create_publish_and_supersede():
    host, _ = _create_tenants()
    client = Client()
    asset = client.post(
        "/api/v1/assets",
        data=json.dumps({"qualified_name": "db.sales", "asset_type": "table"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    asset_id = asset.json()["id"]

    contract = client.post(
        "/api/v1/contracts",
        data=json.dumps(
            {
                "asset_id": asset_id,
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    client.post(f"/api/v1/contracts/{contract.json()['id']}/activate", HTTP_HOST=host)

    v1 = client.post(
        f"/api/v1/assets/{asset_id}/versions",
        data=json.dumps(
            {
                "change_summary": "initial published metadata",
                "change_set": {
                    "ownership": {"owner": "data-team"},
                    "classifications": ["internal"],
                    "schema": {"fields": [{"name": "id", "type": "string"}]},
                },
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert v1.status_code == 201
    v1_id = v1.json()["id"]
    assert v1.json()["version_number"] == 1

    publish_v1 = client.post(
        f"/api/v1/assets/{asset_id}/versions/{v1_id}/publish",
        HTTP_HOST=host,
    )
    assert publish_v1.status_code == 200
    assert publish_v1.json()["status"] == "published"

    v2 = client.post(
        f"/api/v1/assets/{asset_id}/versions",
        data=json.dumps(
            {
                "change_summary": "owner update",
                "change_set": {
                    "ownership": {"owner": "analytics-team"},
                    "classifications": ["internal"],
                    "schema": {"fields": [{"name": "id", "type": "string"}]},
                },
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    v2_id = v2.json()["id"]
    publish_v2 = client.post(
        f"/api/v1/assets/{asset_id}/versions/{v2_id}/publish",
        HTTP_HOST=host,
    )
    assert publish_v2.status_code == 200
    assert publish_v2.json()["status"] == "published"

    versions = client.get(f"/api/v1/assets/{asset_id}/versions", HTTP_HOST=host).json()["items"]
    by_id = {item["id"]: item for item in versions}
    assert by_id[v1_id]["status"] == "superseded"
    assert by_id[v2_id]["status"] == "published"


@pytest.mark.django_db(transaction=True)
def test_asset_version_publish_validations():
    host, _ = _create_tenants()
    client = Client()
    asset = client.post(
        "/api/v1/assets",
        data=json.dumps({"qualified_name": "db.metrics", "asset_type": "table"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    asset_id = asset.json()["id"]

    version = client.post(
        f"/api/v1/assets/{asset_id}/versions",
        data=json.dumps({"change_set": {"classifications": ["internal"]}}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    version_id = version.json()["id"]
    missing_owner = client.post(
        f"/api/v1/assets/{asset_id}/versions/{version_id}/publish",
        HTTP_HOST=host,
    )
    assert missing_owner.status_code == 400
    assert missing_owner.json()["error"] == "owner_required"

    contract = client.post(
        "/api/v1/contracts",
        data=json.dumps(
            {
                "asset_id": asset_id,
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    client.post(f"/api/v1/contracts/{contract.json()['id']}/activate", HTTP_HOST=host)
    incompatible = client.post(
        f"/api/v1/assets/{asset_id}/versions",
        data=json.dumps(
            {
                "change_set": {
                    "ownership": {"owner": "ops-team"},
                    "classifications": ["internal"],
                    "schema": {"fields": [{"name": "id", "type": "int"}]},
                }
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    incompatible_publish = client.post(
        f"/api/v1/assets/{asset_id}/versions/{incompatible.json()['id']}/publish",
        HTTP_HOST=host,
    )
    assert incompatible_publish.status_code == 400
    assert incompatible_publish.json()["error"] == "contract_incompatible_schema_change"


@pytest.mark.django_db(transaction=True)
def test_asset_version_role_and_tenant_scoping(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host_a, host_b = _create_tenants()
    client = Client()
    asset = client.post(
        "/api/v1/assets",
        data=json.dumps(
            {
                "qualified_name": "db.customers",
                "asset_type": "table",
                "owner": "data-team",
                "classifications": ["internal"],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    asset_id = asset.json()["id"]
    created = client.post(
        f"/api/v1/assets/{asset_id}/versions",
        data=json.dumps({"change_set": {"ownership": {"owner": "data-team"}, "classifications": ["internal"]}}),
        content_type="application/json",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert created.status_code == 201
    version_id = created.json()["id"]

    denied_create = client.post(
        f"/api/v1/assets/{asset_id}/versions",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    assert denied_create.status_code == 403

    denied_publish = client.post(
        f"/api/v1/assets/{asset_id}/versions/{version_id}/publish",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_publish.status_code == 403

    not_found_other_tenant = client.get(
        f"/api/v1/assets/{asset_id}/versions",
        HTTP_HOST=host_b,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert not_found_other_tenant.json()["items"] == []
