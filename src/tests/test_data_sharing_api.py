import json
import uuid
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone
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
def test_data_share_lifecycle_and_expiry():
    host, _ = _create_tenants()
    client = Client()
    asset = client.post(
        "/api/v1/assets",
        data=json.dumps({"qualified_name": "db.customers", "asset_type": "table"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    asset_id = asset.json()["id"]

    share = client.post(
        "/api/v1/data-shares",
        data=json.dumps(
            {
                "asset_id": asset_id,
                "consumer_ref": "partner-123",
                "purpose": "analytics",
                "constraints": {
                    "masking_profile": "default",
                    "row_filters": ["region = 'EU'"],
                    "allowed_regions": ["eu-west-1"],
                },
                "linked_access_request_ids": [str(uuid.uuid4())],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert share.status_code == 201
    share_id = share.json()["id"]
    assert share.json()["status"] == "draft"

    approved = client.post(
        f"/api/v1/data-shares/{share_id}/transition",
        data=json.dumps({"action": "approve", "approver": "security-admin"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    active = client.post(
        f"/api/v1/data-shares/{share_id}/transition",
        data=json.dumps({"action": "activate"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert active.status_code == 200
    assert active.json()["status"] == "active"

    revoked = client.post(
        f"/api/v1/data-shares/{share_id}/transition",
        data=json.dumps({"action": "revoke"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    expiring_share = client.post(
        "/api/v1/data-shares",
        data=json.dumps(
            {
                "asset_id": asset_id,
                "consumer_ref": "partner-expired",
                "expires_at": (timezone.now() - timedelta(minutes=5)).isoformat(),
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    expiring_id = expiring_share.json()["id"]
    detail = client.get(f"/api/v1/data-shares/{expiring_id}", HTTP_HOST=host)
    assert detail.status_code == 200
    assert detail.json()["status"] == "expired"


@pytest.mark.django_db(transaction=True)
def test_data_shares_are_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    asset = client.post(
        "/api/v1/assets",
        data=json.dumps({"qualified_name": "db.orders", "asset_type": "table"}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    share = client.post(
        "/api/v1/data-shares",
        data=json.dumps({"asset_id": asset.json()["id"], "consumer_ref": "partner"}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    assert share.status_code == 201
    share_id = share.json()["id"]

    list_a = client.get("/api/v1/data-shares", HTTP_HOST=host_a)
    assert len(list_a.json()["items"]) == 1
    list_b = client.get("/api/v1/data-shares", HTTP_HOST=host_b)
    assert list_b.json()["items"] == []
    detail_b = client.get(f"/api/v1/data-shares/{share_id}", HTTP_HOST=host_b)
    assert detail_b.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_data_share_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()
    asset = client.post(
        "/api/v1/assets",
        data=json.dumps({"qualified_name": "db.events", "asset_type": "table"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    asset_id = asset.json()["id"]

    denied_create = client.post(
        "/api/v1/data-shares",
        data=json.dumps({"asset_id": asset_id, "consumer_ref": "partner"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert denied_create.status_code == 403

    created = client.post(
        "/api/v1/data-shares",
        data=json.dumps({"asset_id": asset_id, "consumer_ref": "partner"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert created.status_code == 201
    share_id = created.json()["id"]

    denied_transition = client.post(
        f"/api/v1/data-shares/{share_id}/transition",
        data=json.dumps({"action": "approve"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_transition.status_code == 403

    allowed_transition = client.post(
        f"/api/v1/data-shares/{share_id}/transition",
        data=json.dumps({"action": "approve"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert allowed_transition.status_code == 200
