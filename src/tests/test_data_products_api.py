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
def test_data_product_lifecycle_requires_active_contracts():
    host, _ = _create_tenants()
    client = Client()
    asset = client.post(
        "/api/v1/assets",
        data=json.dumps({"qualified_name": "db.sales", "asset_type": "table"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert asset.status_code == 201
    asset_id = asset.json()["id"]

    product = client.post(
        "/api/v1/data-products",
        data=json.dumps(
            {
                "name": "Sales KPI",
                "domain": "finance",
                "owner": "analytics-team",
                "asset_ids": [asset_id],
                "sla": {"freshness_minutes": 60},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert product.status_code == 201
    product_id = product.json()["id"]
    assert product.json()["status"] == "draft"

    activation_blocked = client.post(
        f"/api/v1/data-products/{product_id}/activate",
        HTTP_HOST=host,
    )
    assert activation_blocked.status_code == 400
    assert activation_blocked.json()["error"] == "missing_active_contracts"

    contract = client.post(
        "/api/v1/contracts",
        data=json.dumps({"asset_id": asset_id}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert contract.status_code == 201
    activated_contract = client.post(
        f"/api/v1/contracts/{contract.json()['id']}/activate",
        HTTP_HOST=host,
    )
    assert activated_contract.status_code == 200

    activation = client.post(
        f"/api/v1/data-products/{product_id}/activate",
        HTTP_HOST=host,
    )
    assert activation.status_code == 200
    assert activation.json()["status"] == "active"

    retired = client.post(
        f"/api/v1/data-products/{product_id}/retire",
        HTTP_HOST=host,
    )
    assert retired.status_code == 200
    assert retired.json()["status"] == "retired"


@pytest.mark.django_db(transaction=True)
def test_data_products_are_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    created = client.post(
        "/api/v1/data-products",
        data=json.dumps({"name": "Ops Product"}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    product_id = created.json()["id"]

    list_a = client.get("/api/v1/data-products", HTTP_HOST=host_a)
    assert list_a.status_code == 200
    assert len(list_a.json()["items"]) == 1

    list_b = client.get("/api/v1/data-products", HTTP_HOST=host_b)
    assert list_b.status_code == 200
    assert list_b.json()["items"] == []

    detail_b = client.get(f"/api/v1/data-products/{product_id}", HTTP_HOST=host_b)
    assert detail_b.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_data_product_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()
    asset = client.post(
        "/api/v1/assets",
        data=json.dumps({"qualified_name": "db.metrics", "asset_type": "table"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    asset_id = asset.json()["id"]

    denied_create = client.post(
        "/api/v1/data-products",
        data=json.dumps({"name": "Metrics Product", "asset_ids": [asset_id]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert denied_create.status_code == 403

    created = client.post(
        "/api/v1/data-products",
        data=json.dumps(
            {
                "name": "Metrics Product",
                "owner": "platform-team",
                "asset_ids": [asset_id],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert created.status_code == 201
    product_id = created.json()["id"]

    denied_activate = client.post(
        f"/api/v1/data-products/{product_id}/activate",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_activate.status_code == 403

    contract = client.post(
        "/api/v1/contracts",
        data=json.dumps({"asset_id": asset_id}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    allowed_contract_activate = client.post(
        f"/api/v1/contracts/{contract.json()['id']}/activate",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert allowed_contract_activate.status_code == 200

    allowed_activate = client.post(
        f"/api/v1/data-products/{product_id}/activate",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert allowed_activate.status_code == 200
