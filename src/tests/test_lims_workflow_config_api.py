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
                "description": "Schema used for workflow-step binding tests.",
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
                        "name": "Storage slot",
                        "field_key": "storage_slot",
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


@pytest.mark.django_db(transaction=True)
def test_lims_workflow_config_supports_versioning_bindings_and_validation(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-workflow")
    schema_version_id = _create_published_schema(client, host)

    denied = client.post(
        "/api/v1/lims/workflow-config/templates",
        data=json.dumps({"name": "Accession workflow", "code": "accession-workflow"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert denied.status_code == 403

    created = client.post(
        "/api/v1/lims/workflow-config/templates",
        data=json.dumps(
            {
                "name": "Accession workflow",
                "code": "accession-workflow",
                "description": "Tenant-aware workflow template for accession.",
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
                "change_summary": "Define topology",
                "nodes": [
                    {"node_key": "start", "node_type": "start", "title": "Start"},
                    {
                        "node_key": "intake",
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
                        "node_key": "qc",
                        "node_type": "if",
                        "title": "QC decision",
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
                        "node_key": "storage",
                        "node_type": "view",
                        "title": "Storage logging",
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
                    {"source_node_key": "start", "target_node_key": "intake"},
                    {"source_node_key": "intake", "target_node_key": "qc"},
                    {
                        "source_node_key": "qc",
                        "target_node_key": "storage",
                        "priority": 1,
                        "condition": {"field": "qc_decision", "operator": "equals", "value": "accept"},
                    },
                    {
                        "source_node_key": "qc",
                        "target_node_key": "rejected_end",
                        "priority": 2,
                        "condition": {"field": "qc_decision", "operator": "equals", "value": "reject"},
                    },
                    {"source_node_key": "storage", "target_node_key": "accepted_end"},
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert updated.status_code == 200
    assert len(updated.json()["nodes"]) == 6
    assert len(updated.json()["edges"]) == 5

    published = client.post(
        f"/api/v1/lims/workflow-config/templates/{template_id}/versions/{version_id}/publish",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    compiled = published.json()["compiled_definition"]
    assert len(compiled["nodes"]) == 6
    assert len(compiled["edges"]) == 5
    qc_node = next(item for item in compiled["nodes"] if item["node_key"] == "qc")
    assert qc_node["requires_approval"] is True
    assert qc_node["bindings"][0]["binding_type"] == "field_set"

    immutable = client.put(
        f"/api/v1/lims/workflow-config/templates/{template_id}/versions/{version_id}",
        data=json.dumps({"change_summary": "Should fail"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert immutable.status_code == 400
    assert immutable.json()["error"] == "published_versions_are_immutable"

    cloned = client.post(
        f"/api/v1/lims/workflow-config/templates/{template_id}/versions",
        data=json.dumps({"source_version_id": version_id, "change_summary": "Follow-up draft"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert cloned.status_code == 201
    assert cloned.json()["status"] == "draft"
    assert len(cloned.json()["nodes"]) == 6

    invalid_template = client.post(
        "/api/v1/lims/workflow-config/templates",
        data=json.dumps(
            {
                "name": "Invalid workflow",
                "code": "invalid-workflow",
                "change_summary": "Initial draft",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert invalid_template.status_code == 201
    invalid_template_id = invalid_template.json()["id"]
    invalid_version_id = invalid_template.json()["draft_version_id"]
    invalid_updated = client.put(
        f"/api/v1/lims/workflow-config/templates/{invalid_template_id}/versions/{invalid_version_id}",
        data=json.dumps(
            {
                "nodes": [
                    {"node_key": "start", "node_type": "start", "title": "Start"},
                    {"node_key": "dangling", "node_type": "view", "title": "Dangling"},
                ],
                "edges": [
                    {"source_node_key": "start", "target_node_key": "dangling"},
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert invalid_updated.status_code == 200
    invalid_publish = client.post(
        f"/api/v1/lims/workflow-config/templates/{invalid_template_id}/versions/{invalid_version_id}/publish",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert invalid_publish.status_code == 400
    assert invalid_publish.json()["error"] == "workflow_validation_failed"
    assert any(item["code"] == "requires_end_node" for item in invalid_publish.json()["details"])
