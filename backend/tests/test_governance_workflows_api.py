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
def test_governance_policy_lifecycle_and_rollback():
    host, _ = _create_tenants()
    client = Client()

    v1 = client.post(
        "/api/v1/governance/policies",
        data=json.dumps({"name": "retention-policy", "rules": {"days": 30}}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert v1.status_code == 201
    v1_id = v1.json()["id"]

    submitted = client.post(
        f"/api/v1/governance/policies/{v1_id}/transition",
        data=json.dumps({"action": "submit_for_review"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "in_review"

    approved = client.post(
        f"/api/v1/governance/policies/{v1_id}/transition",
        data=json.dumps({"action": "approve"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    active = client.post(
        f"/api/v1/governance/policies/{v1_id}/transition",
        data=json.dumps({"action": "activate"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert active.status_code == 200
    assert active.json()["status"] == "active"

    v2 = client.post(
        "/api/v1/governance/policies",
        data=json.dumps({"name": "retention-policy", "rules": {"days": 60}}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    v2_id = v2.json()["id"]
    for action in ("submit_for_review", "approve", "activate"):
        response = client.post(
            f"/api/v1/governance/policies/{v2_id}/transition",
            data=json.dumps({"action": action}),
            content_type="application/json",
            HTTP_HOST=host,
        )
        assert response.status_code == 200

    rolled_back = client.post(
        f"/api/v1/governance/policies/{v2_id}/transition",
        data=json.dumps({"action": "rollback", "reason": "regression"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["status"] == "rolled_back"
    assert rolled_back.json()["rollback_target_id"] == v1_id

    restored = client.get(
        f"/api/v1/governance/policies/{v1_id}",
        HTTP_HOST=host,
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"


@pytest.mark.django_db(transaction=True)
def test_governance_policies_are_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    created = client.post(
        "/api/v1/governance/policies",
        data=json.dumps({"name": "classification-policy"}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    assert created.status_code == 201
    policy_id = created.json()["id"]

    list_a = client.get("/api/v1/governance/policies", HTTP_HOST=host_a)
    assert list_a.status_code == 200
    assert len(list_a.json()["items"]) == 1

    list_b = client.get("/api/v1/governance/policies", HTTP_HOST=host_b)
    assert list_b.status_code == 200
    assert list_b.json()["items"] == []

    detail_b = client.get(
        f"/api/v1/governance/policies/{policy_id}",
        HTTP_HOST=host_b,
    )
    assert detail_b.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_governance_and_classification_role_enforcement(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()

    denied_policy = client.post(
        "/api/v1/governance/policies",
        data=json.dumps({"name": "classification-policy"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_policy.status_code == 403

    allowed_policy = client.post(
        "/api/v1/governance/policies",
        data=json.dumps({"name": "classification-policy"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert allowed_policy.status_code == 201

    asset = client.post(
        "/api/v1/assets",
        data=json.dumps(
            {
                "qualified_name": "db.sensitive",
                "asset_type": "table",
                "classifications": ["internal"],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert asset.status_code == 201
    asset_id = asset.json()["id"]

    denied_upgrade = client.put(
        f"/api/v1/assets/{asset_id}",
        data=json.dumps({"classifications": ["confidential"]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_upgrade.status_code == 403

    allowed_upgrade = client.put(
        f"/api/v1/assets/{asset_id}",
        data=json.dumps({"classifications": ["confidential"]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor,policy.admin",
    )
    assert allowed_upgrade.status_code == 200

    invalid_classification = client.put(
        f"/api/v1/assets/{asset_id}",
        data=json.dumps({"classifications": ["unknown-level"]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor,policy.admin",
    )
    assert invalid_classification.status_code == 400
    assert invalid_classification.json()["error"] == "unknown_classifications"
