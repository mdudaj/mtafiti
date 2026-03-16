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
def test_connector_run_worker_and_job_paths():
    host, _ = _create_tenants()
    client = Client()
    ing = client.post(
        "/api/v1/ingestions",
        data=json.dumps({"connector": "dbt", "source": {"processed_entities": 11}}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert ing.status_code == 201
    ingestion_id = ing.json()["id"]

    worker_run = client.post(
        "/api/v1/connectors/runs",
        data=json.dumps({"ingestion_id": ingestion_id, "execution_path": "worker"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert worker_run.status_code == 201
    assert worker_run.json()["run"]["status"] == "succeeded"
    assert worker_run.json()["run"]["progress"]["processed_entities"] == 11

    failed_ing = client.post(
        "/api/v1/ingestions",
        data=json.dumps(
            {"connector": "dbt", "source": {"force_status": "failed", "error_message": "network"}}
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert failed_ing.status_code == 201
    failed_run = client.post(
        "/api/v1/connectors/runs",
        data=json.dumps(
            {"ingestion_id": failed_ing.json()["id"], "execution_path": "job"}
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert failed_run.status_code == 201
    assert failed_run.json()["run"]["status"] == "failed"

    listed = client.get("/api/v1/connectors/runs", HTTP_HOST=host)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2

    ing_detail = client.get(
        f"/api/v1/ingestions/{ingestion_id}",
        HTTP_HOST=host,
    )
    assert ing_detail.status_code == 200
    assert ing_detail.json()["execution"]["state"] == "succeeded"
    assert ing_detail.json()["execution"]["retry_count"] == 0


@pytest.mark.django_db(transaction=True)
def test_connector_runs_are_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    ing_a = client.post(
        "/api/v1/ingestions",
        data=json.dumps({"connector": "dbt", "source": {}}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    run_a = client.post(
        "/api/v1/connectors/runs",
        data=json.dumps({"ingestion_id": ing_a.json()["id"]}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    assert run_a.status_code == 201
    run_id = run_a.json()["run"]["id"]

    assert len(client.get("/api/v1/connectors/runs", HTTP_HOST=host_a).json()["items"]) == 1
    assert client.get("/api/v1/connectors/runs", HTTP_HOST=host_b).json()["items"] == []
    assert (
        client.post(
            f"/api/v1/connectors/runs/{run_id}/cancel",
            HTTP_HOST=host_b,
        ).status_code
        == 404
    )


@pytest.mark.django_db(transaction=True)
def test_connector_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()
    ing = client.post(
        "/api/v1/ingestions",
        data=json.dumps({"connector": "dbt", "source": {}}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    ingestion_id = ing.json()["id"]

    denied_run = client.post(
        "/api/v1/connectors/runs",
        data=json.dumps({"ingestion_id": ingestion_id}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert denied_run.status_code == 403

    allowed_run = client.post(
        "/api/v1/connectors/runs",
        data=json.dumps({"ingestion_id": ingestion_id}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert allowed_run.status_code == 201

    denied_cancel = client.post(
        f"/api/v1/connectors/runs/{allowed_run.json()['run']['id']}/cancel",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert denied_cancel.status_code == 403

    denied_read = client.get("/api/v1/connectors/runs", HTTP_HOST=host)
    assert denied_read.status_code == 403
    allowed_read = client.get(
        "/api/v1/connectors/runs",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert allowed_read.status_code == 200
