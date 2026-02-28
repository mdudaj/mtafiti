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
def test_orchestration_workflow_and_run_lifecycle():
    host, _ = _create_tenants()
    client = Client()
    ingestion = client.post(
        "/api/v1/ingestions",
        data=json.dumps({"connector": "dbt", "source": {"processed_entities": 5}}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    ingestion_id = ingestion.json()["id"]
    workflow = client.post(
        "/api/v1/orchestration/workflows",
        data=json.dumps(
            {
                "name": "nightly-refresh",
                "trigger_type": "schedule",
                "trigger_value": "0 2 * * *",
                "steps": [{"step_id": "extract", "ingestion_id": ingestion_id}],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert workflow.status_code == 201
    workflow_id = workflow.json()["id"]

    queued_run = client.post(
        "/api/v1/orchestration/runs",
        data=json.dumps({"workflow_id": workflow_id, "trigger_context": {"mode": "manual"}}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert queued_run.status_code == 201
    run_id = queued_run.json()["id"]
    assert queued_run.json()["status"] == "queued"

    started_run = client.post(
        f"/api/v1/orchestration/runs/{run_id}/transition",
        data=json.dumps({"action": "start"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert started_run.status_code == 200
    assert started_run.json()["status"] == "succeeded"
    assert len(started_run.json()["step_results"]) == 1
    assert started_run.json()["step_results"][0]["status"] == "succeeded"


@pytest.mark.django_db(transaction=True)
def test_orchestration_is_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    ingestion = client.post(
        "/api/v1/ingestions",
        data=json.dumps({"connector": "dbt", "source": {}}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    workflow = client.post(
        "/api/v1/orchestration/workflows",
        data=json.dumps(
            {
                "name": "tenant-a-only",
                "steps": [{"step_id": "step-a", "ingestion_id": ingestion.json()["id"]}],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    run = client.post(
        "/api/v1/orchestration/runs",
        data=json.dumps({"workflow_id": workflow.json()["id"]}),
        content_type="application/json",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    run_id = run.json()["id"]

    other_tenant_runs = client.get("/api/v1/orchestration/runs", HTTP_HOST=host_b)
    assert other_tenant_runs.status_code == 200
    assert other_tenant_runs.json()["items"] == []

    not_found = client.post(
        f"/api/v1/orchestration/runs/{run_id}/transition",
        data=json.dumps({"action": "start"}),
        content_type="application/json",
        HTTP_HOST=host_b,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert not_found.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_orchestration_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()
    ingestion = client.post(
        "/api/v1/ingestions",
        data=json.dumps({"connector": "dbt", "source": {}}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    ingestion_id = ingestion.json()["id"]

    denied_workflow = client.post(
        "/api/v1/orchestration/workflows",
        data=json.dumps({"name": "wf", "steps": [{"step_id": "s1", "ingestion_id": ingestion_id}]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_workflow.status_code == 403

    workflow = client.post(
        "/api/v1/orchestration/workflows",
        data=json.dumps({"name": "wf", "steps": [{"step_id": "s1", "ingestion_id": ingestion_id}]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert workflow.status_code == 201

    denied_run = client.post(
        "/api/v1/orchestration/runs",
        data=json.dumps({"workflow_id": workflow.json()["id"]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert denied_run.status_code == 403

    run = client.post(
        "/api/v1/orchestration/runs",
        data=json.dumps({"workflow_id": workflow.json()["id"]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert run.status_code == 201

    denied_transition = client.post(
        f"/api/v1/orchestration/runs/{run.json()['id']}/transition",
        data=json.dumps({"action": "cancel"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_transition.status_code == 403
