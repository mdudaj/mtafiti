import json
import uuid
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone
from django_tenants.utils import schema_context

from core.models import AgentRun
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
    return host_a, tenant_a.schema_name, host_b


@pytest.mark.django_db(transaction=True)
def test_agent_run_lifecycle_and_cancellation():
    host, _, _ = _create_tenants()
    client = Client()
    created = client.post(
        "/api/v1/agent/runs",
        data=json.dumps(
            {
                "prompt": "Summarize data quality alerts",
                "allowed_tools": ["catalog.search", "quality.read"],
                "timeout_seconds": 120,
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
        HTTP_X_USER_ID="user-1",
    )
    assert created.status_code == 201
    run_id = created.json()["id"]
    assert created.json()["status"] == "queued"

    started = client.post(
        f"/api/v1/agent/runs/{run_id}/transition",
        data=json.dumps({"action": "start"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert started.status_code == 200
    assert started.json()["status"] == "running"

    cancelled = client.post(
        f"/api/v1/agent/runs/{run_id}/transition",
        data=json.dumps({"action": "cancel"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


@pytest.mark.django_db(transaction=True)
def test_agent_run_timeout_materialization():
    host, schema_name, _ = _create_tenants()
    client = Client()
    created = client.post(
        "/api/v1/agent/runs",
        data=json.dumps(
            {
                "prompt": "Find stale contracts",
                "allowed_tools": ["contract.read"],
                "timeout_seconds": 5,
                "start_now": True,
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    run_id = created.json()["id"]

    with schema_context(schema_name):
        AgentRun.objects.filter(id=run_id).update(
            started_at=timezone.now() - timedelta(seconds=10)
        )

    timed_out = client.post(
        f"/api/v1/agent/runs/{run_id}/transition",
        data=json.dumps({"action": "materialize_timeouts"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert timed_out.status_code == 200
    assert timed_out.json()["status"] == "timed_out"


@pytest.mark.django_db(transaction=True)
def test_agent_run_validation_role_and_tenant_scoping(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host_a, _, host_b = _create_tenants()
    client = Client()
    invalid_tools = client.post(
        "/api/v1/agent/runs",
        data=json.dumps(
            {
                "prompt": "Test",
                "allowed_tools": ["shell.exec"],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert invalid_tools.status_code == 400
    assert invalid_tools.json()["error"] == "invalid_allowed_tools"

    denied = client.post(
        "/api/v1/agent/runs",
        data=json.dumps(
            {
                "prompt": "Test",
                "allowed_tools": ["catalog.search"],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert denied.status_code == 403

    created = client.post(
        "/api/v1/agent/runs",
        data=json.dumps(
            {
                "prompt": "Find lineage gaps",
                "allowed_tools": ["lineage.read"],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    run_id = created.json()["id"]

    other_tenant = client.get(
        "/api/v1/agent/runs",
        HTTP_HOST=host_b,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert other_tenant.status_code == 200
    assert other_tenant.json()["items"] == []

    not_found = client.post(
        f"/api/v1/agent/runs/{run_id}/transition",
        data=json.dumps({"action": "start"}),
        content_type="application/json",
        HTTP_HOST=host_b,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert not_found.status_code == 404
