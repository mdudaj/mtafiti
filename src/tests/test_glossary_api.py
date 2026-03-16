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
def test_glossary_term_lifecycle_and_asset_link():
    host, _ = _create_tenants()
    client = Client()

    created = client.post(
        "/api/v1/glossary/terms",
        data=json.dumps(
            {
                "name": "Customer",
                "definition": "An entity that purchases services.",
                "owners": ["data-office"],
                "stewards": ["governance-team"],
                "classifications": ["internal"],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    term_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    approved = client.post(
        f"/api/v1/glossary/terms/{term_id}/approve",
        HTTP_HOST=host,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    asset = client.post(
        "/api/v1/assets",
        data=json.dumps({"qualified_name": "db.customers", "asset_type": "table"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert asset.status_code == 201
    asset_id = asset.json()["id"]

    linked = client.post(
        f"/api/v1/assets/{asset_id}/terms/{term_id}",
        HTTP_HOST=host,
    )
    assert linked.status_code == 200
    assert linked.json()["related_asset_ids"] == [asset_id]

    deprecated = client.post(
        f"/api/v1/glossary/terms/{term_id}/deprecate",
        HTTP_HOST=host,
    )
    assert deprecated.status_code == 200
    assert deprecated.json()["status"] == "deprecated"

    blocked_link = client.post(
        f"/api/v1/assets/{asset_id}/terms/{term_id}",
        HTTP_HOST=host,
    )
    assert blocked_link.status_code == 400
    assert blocked_link.json()["error"] == "term_not_approved"


@pytest.mark.django_db(transaction=True)
def test_glossary_is_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()

    created = client.post(
        "/api/v1/glossary/terms",
        data=json.dumps({"name": "Order"}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    term_id = created.json()["id"]

    list_a = client.get("/api/v1/glossary/terms", HTTP_HOST=host_a)
    assert list_a.status_code == 200
    assert len(list_a.json()["items"]) == 1

    list_b = client.get("/api/v1/glossary/terms", HTTP_HOST=host_b)
    assert list_b.status_code == 200
    assert list_b.json()["items"] == []

    detail_b = client.get(f"/api/v1/glossary/terms/{term_id}", HTTP_HOST=host_b)
    assert detail_b.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_glossary_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()

    denied_create = client.post(
        "/api/v1/glossary/terms",
        data=json.dumps({"name": "Invoice"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert denied_create.status_code == 403

    created = client.post(
        "/api/v1/glossary/terms",
        data=json.dumps({"name": "Invoice"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert created.status_code == 201
    term_id = created.json()["id"]

    denied_approve = client.post(
        f"/api/v1/glossary/terms/{term_id}/approve",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_approve.status_code == 403

    approved = client.post(
        f"/api/v1/glossary/terms/{term_id}/approve",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert approved.status_code == 200

    asset = client.post(
        "/api/v1/assets",
        data=json.dumps({"qualified_name": "db.invoices", "asset_type": "table"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    asset_id = asset.json()["id"]

    denied_link = client.post(
        f"/api/v1/assets/{asset_id}/terms/{term_id}",
        HTTP_HOST=host,
    )
    assert denied_link.status_code == 403

    allowed_link = client.post(
        f"/api/v1/assets/{asset_id}/terms/{term_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert allowed_link.status_code == 200
