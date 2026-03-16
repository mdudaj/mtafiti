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
def test_workflow_definition_run_and_transition_lifecycle():
    host, _ = _create_tenants()
    client = Client()

    definition = client.post(
        "/api/v1/workflows/definitions",
        data=json.dumps({"name": "Policy Review", "domain_ref": "policy"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert definition.status_code == 201
    definition_id = definition.json()["id"]

    run = client.post(
        "/api/v1/workflows/runs",
        data=json.dumps(
            {
                "definition_id": definition_id,
                "subject_ref": "policy:retention-v2",
                "payload": {"ticket": "GOV-101"},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="editor@example.com",
    )
    assert run.status_code == 201
    run_id = run.json()["id"]
    assert run.json()["status"] == "draft"

    submitted = client.post(
        f"/api/v1/workflows/runs/{run_id}/transition",
        data=json.dumps({"action": "submit", "assignee": "reviewer@example.com"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "in_review"

    tasks = client.get(f"/api/v1/workflows/runs/{run_id}/tasks", HTTP_HOST=host)
    assert tasks.status_code == 200
    assert len(tasks.json()["items"]) == 1

    approved = client.post(
        f"/api/v1/workflows/runs/{run_id}/transition",
        data=json.dumps({"action": "approve"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="approver@example.com",
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    active = client.post(
        f"/api/v1/workflows/runs/{run_id}/transition",
        data=json.dumps({"action": "activate"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert active.status_code == 200
    assert active.json()["status"] == "active"

    superseded = client.post(
        f"/api/v1/workflows/runs/{run_id}/transition",
        data=json.dumps({"action": "supersede"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert superseded.status_code == 200
    assert superseded.json()["status"] == "superseded"


@pytest.mark.django_db(transaction=True)
def test_workflow_ui_is_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    definition = client.post(
        "/api/v1/workflows/definitions",
        data=json.dumps({"name": "Policy Review"}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    assert definition.status_code == 201
    definition_id = definition.json()["id"]
    run = client.post(
        "/api/v1/workflows/runs",
        data=json.dumps({"definition_id": definition_id}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    assert run.status_code == 201
    run_id = run.json()["id"]

    assert len(client.get("/api/v1/workflows/definitions", HTTP_HOST=host_a).json()["items"]) == 1
    assert client.get("/api/v1/workflows/definitions", HTTP_HOST=host_b).json()["items"] == []
    assert client.get(f"/api/v1/workflows/runs/{run_id}/tasks", HTTP_HOST=host_b).json()["items"] == []
    assert (
        client.post(
            f"/api/v1/workflows/runs/{run_id}/transition",
            data=json.dumps({"action": "submit"}),
            content_type="application/json",
            HTTP_HOST=host_b,
        ).status_code
        == 404
    )


@pytest.mark.django_db(transaction=True)
def test_workflow_ui_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()

    denied_definition = client.post(
        "/api/v1/workflows/definitions",
        data=json.dumps({"name": "Policy Review"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_definition.status_code == 403

    definition = client.post(
        "/api/v1/workflows/definitions",
        data=json.dumps({"name": "Policy Review"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert definition.status_code == 201
    definition_id = definition.json()["id"]

    denied_run = client.post(
        "/api/v1/workflows/runs",
        data=json.dumps({"definition_id": definition_id}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert denied_run.status_code == 403

    run = client.post(
        "/api/v1/workflows/runs",
        data=json.dumps({"definition_id": definition_id}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert run.status_code == 201
    run_id = run.json()["id"]

    denied_submit = client.post(
        f"/api/v1/workflows/runs/{run_id}/transition",
        data=json.dumps({"action": "submit"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert denied_submit.status_code == 403

    submitted = client.post(
        f"/api/v1/workflows/runs/{run_id}/transition",
        data=json.dumps({"action": "submit"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert submitted.status_code == 200

    denied_approve = client.post(
        f"/api/v1/workflows/runs/{run_id}/transition",
        data=json.dumps({"action": "approve"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_approve.status_code == 403

    allowed_approve = client.post(
        f"/api/v1/workflows/runs/{run_id}/transition",
        data=json.dumps({"action": "approve"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert allowed_approve.status_code == 200
