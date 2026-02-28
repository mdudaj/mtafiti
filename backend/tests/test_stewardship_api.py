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
def test_stewardship_item_lifecycle():
    host, _ = _create_tenants()
    client = Client()
    created = client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {
                "item_type": "quality_exception",
                "subject_ref": "asset:db.customers",
                "severity": "high",
                "assignee": "triage@example.com",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="creator@example.com",
    )
    assert created.status_code == 201
    item_id = created.json()["id"]
    assert created.json()["status"] == "open"

    assigned = client.post(
        f"/api/v1/stewardship/items/{item_id}/transition",
        data=json.dumps({"action": "assign", "assignee": "steward@example.com"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
        HTTP_X_USER_ID="policy@example.com",
    )
    assert assigned.status_code == 200
    assert assigned.json()["assignee"] == "steward@example.com"

    reviewing = client.post(
        f"/api/v1/stewardship/items/{item_id}/transition",
        data=json.dumps({"action": "start_review"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert reviewing.status_code == 200
    assert reviewing.json()["status"] == "in_review"

    resolved = client.post(
        f"/api/v1/stewardship/items/{item_id}/transition",
        data=json.dumps({"action": "resolve", "resolution": {"ticket": "STW-101"}}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolution"] == {"ticket": "STW-101"}

    reopened = client.post(
        f"/api/v1/stewardship/items/{item_id}/transition",
        data=json.dumps({"action": "reopen"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"
    assert reopened.json()["resolution"] == {}


@pytest.mark.django_db(transaction=True)
def test_stewardship_tenant_scoping():
    host_a, host_b = _create_tenants()
    client = Client()
    created = client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {
                "item_type": "contract_violation",
                "subject_ref": "contract:orders-v2",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    items_other_tenant = client.get("/api/v1/stewardship/items", HTTP_HOST=host_b)
    assert items_other_tenant.status_code == 200
    assert items_other_tenant.json()["items"] == []

    not_found = client.post(
        f"/api/v1/stewardship/items/{item_id}/transition",
        data=json.dumps({"action": "start_review"}),
        content_type="application/json",
        HTTP_HOST=host_b,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert not_found.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_stewardship_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()

    denied_create = client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {
                "item_type": "retention_hold",
                "subject_ref": "hold:legal-1",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert denied_create.status_code == 403

    created = client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {
                "item_type": "retention_hold",
                "subject_ref": "hold:legal-1",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    denied_transition = client.post(
        f"/api/v1/stewardship/items/{item_id}/transition",
        data=json.dumps({"action": "start_review"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_transition.status_code == 403

    allowed_transition = client.post(
        f"/api/v1/stewardship/items/{item_id}/transition",
        data=json.dumps({"action": "start_review"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert allowed_transition.status_code == 200
