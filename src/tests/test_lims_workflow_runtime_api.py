import json
import uuid

import pytest
from django.test import Client


def _create_lims_host(client: Client, route_slug: str) -> str:
    control_host = "control.example"
    created_tenant = client.post(
        "/api/v1/tenants",
        data=json.dumps(
            {
                "name": f"Tenant {uuid.uuid4().hex[:6]}",
                "domain": f"tenant-{uuid.uuid4().hex[:6]}.example",
            }
        ),
        content_type="application/json",
        HTTP_HOST=control_host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert created_tenant.status_code == 201
    tenant_id = created_tenant.json()["id"]
    created_route = client.post(
        "/api/v1/tenants/services",
        data=json.dumps(
            {
                "tenant_id": tenant_id,
                "service_key": "lims",
                "tenant_slug": route_slug,
                "base_domain": "mtafiti.apps.nimr.or.tz",
            }
        ),
        content_type="application/json",
        HTTP_HOST=control_host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert created_route.status_code == 201
    return created_route.json()["domain"]


def _create_published_schema(client: Client, host: str) -> str:
    schema = client.post(
        "/api/v1/lims/metadata/schemas",
        data=json.dumps(
            {
                "name": "Accession task schema",
                "code": "accession-task-schema",
                "description": "Schema used for workflow runtime tests.",
                "purpose": "Workflow task capture",
                "change_summary": "Initial draft",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert schema.status_code == 201
    schema_id = schema.json()["id"]
    version_id = schema.json()["draft_version_id"]
    updated = client.put(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions/{version_id}",
        data=json.dumps(
            {
                "fields": [
                    {
                        "name": "Subject identifier",
                        "field_key": "subject_identifier",
                        "field_type": "text",
                        "required": True,
                        "config": {"ui_step": "intake"},
                    },
                    {
                        "name": "QC decision",
                        "field_key": "qc_decision",
                        "field_type": "text",
                        "required": True,
                        "config": {"ui_step": "qc"},
                    },
                    {
                        "name": "Storage reference",
                        "field_key": "storage_reference",
                        "field_type": "text",
                        "required": False,
                        "config": {"ui_step": "storage"},
                    },
                ]
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert updated.status_code == 200
    published = client.post(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions/{version_id}/publish",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert published.status_code == 200
    return version_id


def _create_published_workflow(client: Client, host: str, schema_version_id: str) -> str:
    created = client.post(
        "/api/v1/lims/workflow-config/templates",
        data=json.dumps(
            {
                "name": "Sample accession workflow",
                "code": "sample-accession",
                "description": "Workflow used for runtime execution tests.",
                "purpose": "Accessioning",
                "change_summary": "Initial draft",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert created.status_code == 201
    template_id = created.json()["id"]
    version_id = created.json()["draft_version_id"]
    updated = client.put(
        f"/api/v1/lims/workflow-config/templates/{template_id}/versions/{version_id}",
        data=json.dumps(
            {
                "change_summary": "Define runtime topology",
                "nodes": [
                    {"node_key": "start", "node_type": "start", "title": "Start"},
                    {
                        "node_key": "intake_capture",
                        "node_type": "view",
                        "title": "Intake capture",
                        "assignment_role": "lims.operator",
                        "permission_key": "lims.workflow_task.execute",
                        "step_bindings": [
                            {
                                "schema_version_id": schema_version_id,
                                "binding_type": "ui_step",
                                "ui_step": "intake",
                            }
                        ],
                    },
                    {
                        "node_key": "qc_decision",
                        "node_type": "if",
                        "title": "QC decision",
                        "assignment_role": "lims.operator",
                        "permission_key": "lims.workflow_task.execute",
                        "requires_approval": True,
                        "approval_role": "lims.qa",
                        "step_bindings": [
                            {
                                "schema_version_id": schema_version_id,
                                "binding_type": "field_set",
                                "field_keys": ["qc_decision"],
                            }
                        ],
                    },
                    {
                        "node_key": "storage_logging",
                        "node_type": "view",
                        "title": "Storage logging",
                        "assignment_role": "lims.operator",
                        "permission_key": "lims.workflow_task.execute",
                        "step_bindings": [
                            {
                                "schema_version_id": schema_version_id,
                                "binding_type": "ui_step",
                                "ui_step": "storage",
                            }
                        ],
                    },
                    {"node_key": "accepted_end", "node_type": "end", "title": "Accepted end"},
                    {"node_key": "rejected_end", "node_type": "end", "title": "Rejected end"},
                ],
                "edges": [
                    {"source_node_key": "start", "target_node_key": "intake_capture"},
                    {"source_node_key": "intake_capture", "target_node_key": "qc_decision"},
                    {
                        "source_node_key": "qc_decision",
                        "target_node_key": "storage_logging",
                        "priority": 1,
                        "condition": {"field": "qc_decision", "operator": "equals", "value": "accept"},
                    },
                    {
                        "source_node_key": "qc_decision",
                        "target_node_key": "rejected_end",
                        "priority": 2,
                        "condition": {"field": "qc_decision", "operator": "equals", "value": "reject"},
                    },
                    {"source_node_key": "storage_logging", "target_node_key": "accepted_end"},
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert updated.status_code == 200
    published = client.post(
        f"/api/v1/lims/workflow-config/templates/{template_id}/versions/{version_id}/publish",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert published.status_code == 200
    return version_id


def _create_published_operation(client: Client, host: str, workflow_version_id: str) -> tuple[str, str]:
    created = client.post(
        "/api/v1/lims/operations",
        data=json.dumps(
            {
                "name": "Sample accession",
                "code": "sample-accession",
                "module_scope": "lims",
                "description": "Governed accession operation.",
                "purpose": "Accessioning",
                "workflow_version_id": workflow_version_id,
                "runtime_defaults": {"source_mode": "single"},
                "change_summary": "Initial draft",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert created.status_code == 201
    operation_id = created.json()["id"]
    version_id = created.json()["draft_version_id"]
    published = client.post(
        f"/api/v1/lims/operations/{operation_id}/versions/{version_id}/publish",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert published.status_code == 200
    return operation_id, version_id


@pytest.mark.django_db(transaction=True)
def test_lims_workflow_runtime_executes_accept_and_reject_paths(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-runtime")
    schema_version_id = _create_published_schema(client, host)
    workflow_version_id = _create_published_workflow(client, host, schema_version_id)
    operation_id, operation_version_id = _create_published_operation(client, host, workflow_version_id)

    created_run = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs",
        data=json.dumps(
            {
                "operation_version_id": operation_version_id,
                "source_mode": "single",
                "subject_identifier": "SUBJ-001",
                "external_identifier": "EXT-001",
                "context": {"intake_mode": "bench"},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
        HTTP_X_USER_ID="manager-1",
    )
    assert created_run.status_code == 201
    run_id = created_run.json()["id"]
    assert created_run.json()["status"] == "active"
    assert created_run.json()["workflow_version_id"] == workflow_version_id
    intake_task = next(item for item in created_run.json()["tasks"] if item["node_key"] == "intake_capture")

    intake_submitted = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{run_id}/tasks/{intake_task['id']}/submit",
        data=json.dumps(
            {
                "payload": {
                    "subject_identifier": "SUBJ-001",
                    "barcode": "BC-001",
                }
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )
    assert intake_submitted.status_code == 200
    qc_task = next(item for item in intake_submitted.json()["tasks"] if item["node_key"] == "qc_decision")
    assert qc_task["status"] == "open"

    qc_submitted = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{run_id}/tasks/{qc_task['id']}/submit",
        data=json.dumps({"payload": {"qc_decision": "accept"}}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )
    assert qc_submitted.status_code == 200
    qc_after_submit = next(item for item in qc_submitted.json()["tasks"] if item["node_key"] == "qc_decision")
    assert qc_after_submit["status"] == "awaiting_approval"

    qc_approved = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{run_id}/tasks/{qc_task['id']}/approve",
        data=json.dumps({"outcome": "approved", "meaning": "QA accepted decision"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.qa",
        HTTP_X_USER_ID="qa-1",
    )
    assert qc_approved.status_code == 200
    storage_task = next(item for item in qc_approved.json()["tasks"] if item["node_key"] == "storage_logging")
    assert storage_task["status"] == "open"

    storage_submitted = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{run_id}/tasks/{storage_task['id']}/submit",
        data=json.dumps({"payload": {"storage_reference": "FREEZER-A1"}}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )
    assert storage_submitted.status_code == 200
    assert storage_submitted.json()["status"] == "completed"
    assert any(item["action"] == "stored" for item in storage_submitted.json()["material_usages"])
    assert any(item["outcome"] == "approved" for item in storage_submitted.json()["approvals"])

    rejected_run = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs",
        data=json.dumps(
            {
                "operation_version_id": operation_version_id,
                "source_mode": "single",
                "subject_identifier": "SUBJ-002",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
        HTTP_X_USER_ID="manager-1",
    )
    assert rejected_run.status_code == 201
    rejected_run_id = rejected_run.json()["id"]
    rejected_intake = next(item for item in rejected_run.json()["tasks"] if item["node_key"] == "intake_capture")
    client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{rejected_run_id}/tasks/{rejected_intake['id']}/submit",
        data=json.dumps({"payload": {"subject_identifier": "SUBJ-002"}}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )
    rejected_run_detail = client.get(
        f"/api/v1/lims/operations/{operation_id}/runs/{rejected_run_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    rejected_qc = next(item for item in rejected_run_detail.json()["tasks"] if item["node_key"] == "qc_decision")
    rejected_submitted = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{rejected_run_id}/tasks/{rejected_qc['id']}/submit",
        data=json.dumps({"payload": {"qc_decision": "reject", "reason": "damaged sample"}}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )
    assert rejected_submitted.status_code == 200
    rejected_approved = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{rejected_run_id}/tasks/{rejected_qc['id']}/approve",
        data=json.dumps({"outcome": "approved", "meaning": "QA confirmed rejection"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.qa",
        HTTP_X_USER_ID="qa-1",
    )
    assert rejected_approved.status_code == 200
    assert rejected_approved.json()["status"] == "rejected"
    assert any(item["action"] == "rejected" for item in rejected_approved.json()["material_usages"])
