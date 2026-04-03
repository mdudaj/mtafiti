import json
import uuid

import pytest
from django.test import Client

from lims.models import OperationVersion


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


@pytest.mark.django_db(transaction=True)
def test_lims_reference_sample_accession_provision_is_idempotent(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-reference-accession")

    provisioned = client.post(
        "/api/v1/lims/reference/operations/sample-accession/provision",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert provisioned.status_code == 200
    payload = provisioned.json()
    assert payload["reference_operation"] == "sample-accession"
    assert payload["created"] is True
    assert payload["form_package"]["code"] == "sample-accession-package"
    assert payload["form_package_version"]["status"] == "published"
    assert payload["workflow_template"]["code"] == "sample-accession"
    assert payload["workflow_version"]["status"] == "published"
    assert payload["operation_definition"]["code"] == "sample-accession"
    assert payload["operation_version"]["status"] == "published"
    assert (
        payload["operation_version"]["sop_version_label"]
        == "sample-accession-reference-sop-v1"
    )
    assert payload["operation_version"]["runtime_defaults"]["source_modes"] == [
        "single",
        "batch",
        "edc_import",
    ]
    assert (
        payload["operation_version"]["runtime_defaults"]["sop_context_required"] is True
    )
    assert [
        section["section_key"]
        for section in payload["form_package_version"]["compiled_projection"][
            "sections"
        ]
    ] == [
        "intake",
        "qc",
        "storage",
        "rejection",
    ]
    qc_node = next(
        item
        for item in payload["workflow_version"]["compiled_definition"]["nodes"]
        if item["node_key"] == "qc_decision"
    )
    assert qc_node["approval"]["required"] is True
    assert qc_node["bindings"][0]["item_keys"] == [
        "qc_decision",
        "qc_notes",
        "rejection_code",
        "reason",
    ]

    provisioned_again = client.post(
        "/api/v1/lims/reference/operations/sample-accession/provision",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert provisioned_again.status_code == 200
    payload_again = provisioned_again.json()
    assert payload_again["created"] is False
    assert (
        payload_again["form_package_version"]["id"]
        == payload["form_package_version"]["id"]
    )
    assert payload_again["workflow_version"]["id"] == payload["workflow_version"]["id"]
    assert (
        payload_again["operation_version"]["id"] == payload["operation_version"]["id"]
    )


@pytest.mark.django_db(transaction=True)
def test_lims_reference_sample_accession_provision_rejects_drifted_published_bundle(
    monkeypatch,
):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-reference-accession-drift")

    provisioned = client.post(
        "/api/v1/lims/reference/operations/sample-accession/provision",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert provisioned.status_code == 200

    operation_version = OperationVersion.objects.get(
        definition__code="sample-accession",
        status=OperationVersion.Status.PUBLISHED,
    )
    operation_version.sop_version_label = ""
    operation_version.save(update_fields=["sop_version_label", "updated_at"])

    reprovisioned = client.post(
        "/api/v1/lims/reference/operations/sample-accession/provision",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert reprovisioned.status_code == 400
    assert (
        reprovisioned.json()["error"]
        == "sample_accession_reference_bundle_invariants_failed"
    )
    assert {
        "field": "operation_version.sop_version_label",
        "code": "reference_sop_version_label_mismatch",
    } in reprovisioned.json()["details"]


@pytest.mark.django_db(transaction=True)
def test_lims_reference_sample_accession_bundle_executes_runtime_paths(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-reference-runtime")

    provisioned = client.post(
        "/api/v1/lims/reference/operations/sample-accession/provision",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert provisioned.status_code == 200
    operation = provisioned.json()["operation_definition"]
    operation_version_id = provisioned.json()["operation_version"]["id"]
    operation_id = operation["id"]

    single_run = client.post(
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
    assert single_run.status_code == 201
    single_payload = single_run.json()
    assert single_payload["source_mode"] == "single"
    intake_task = next(
        item for item in single_payload["tasks"] if item["node_key"] == "intake_capture"
    )

    intake_submitted = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{single_payload['id']}/tasks/{intake_task['id']}/submit",
        data=json.dumps(
            {
                "payload": {
                    "subject_identifier": "SUBJ-001",
                    "external_identifier": "EXT-001",
                    "received_at": "2026-03-20",
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
    qc_task = next(
        item
        for item in intake_submitted.json()["tasks"]
        if item["node_key"] == "qc_decision"
    )

    qc_submitted = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{single_payload['id']}/tasks/{qc_task['id']}/submit",
        data=json.dumps(
            {"payload": {"qc_decision": "accept", "qc_notes": "Visual QC ok"}}
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )
    assert qc_submitted.status_code == 200
    assert (
        next(
            item
            for item in qc_submitted.json()["tasks"]
            if item["node_key"] == "qc_decision"
        )["status"]
        == "awaiting_approval"
    )

    qc_approved = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{single_payload['id']}/tasks/{qc_task['id']}/approve",
        data=json.dumps({"outcome": "approved", "meaning": "QA accepted accession QC"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.qa",
        HTTP_X_USER_ID="qa-1",
    )
    assert qc_approved.status_code == 200
    storage_task = next(
        item
        for item in qc_approved.json()["tasks"]
        if item["node_key"] == "storage_logging"
    )

    storage_submitted = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{single_payload['id']}/tasks/{storage_task['id']}/submit",
        data=json.dumps(
            {"payload": {"storage_reference": "FREEZER-A1", "storage_notes": "Shelf 2"}}
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )
    assert storage_submitted.status_code == 200
    assert storage_submitted.json()["status"] == "completed"
    assert any(
        item["action"] == "stored"
        for item in storage_submitted.json()["material_usages"]
    )

    batch_run = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs",
        data=json.dumps(
            {
                "operation_version_id": operation_version_id,
                "source_mode": "batch",
                "source_reference": "MANIFEST-001",
                "subject_identifier": "SUBJ-002",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
        HTTP_X_USER_ID="manager-1",
    )
    assert batch_run.status_code == 201
    batch_payload = batch_run.json()
    assert batch_payload["source_mode"] == "batch"
    batch_intake = next(
        item for item in batch_payload["tasks"] if item["node_key"] == "intake_capture"
    )
    batch_intake_submitted = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{batch_payload['id']}/tasks/{batch_intake['id']}/submit",
        data=json.dumps(
            {"payload": {"subject_identifier": "SUBJ-002", "received_at": "2026-03-20"}}
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )
    assert batch_intake_submitted.status_code == 200
    batch_qc = next(
        item
        for item in batch_intake_submitted.json()["tasks"]
        if item["node_key"] == "qc_decision"
    )
    batch_qc_submitted = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{batch_payload['id']}/tasks/{batch_qc['id']}/submit",
        data=json.dumps(
            {
                "payload": {
                    "qc_decision": "reject",
                    "rejection_code": "damaged",
                    "reason": "Tube leaked",
                }
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )
    assert batch_qc_submitted.status_code == 200
    batch_qc_approved = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{batch_payload['id']}/tasks/{batch_qc['id']}/approve",
        data=json.dumps({"outcome": "approved", "meaning": "QA confirmed rejection"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.qa",
        HTTP_X_USER_ID="qa-1",
    )
    assert batch_qc_approved.status_code == 200
    assert batch_qc_approved.json()["status"] == "rejected"
    assert any(
        item["action"] == "rejected"
        for item in batch_qc_approved.json()["material_usages"]
    )
    assert batch_qc_approved.json()["qc_results"][0]["decision"] == "reject"
    assert batch_qc_approved.json()["qc_results"][0]["notes"] == "Tube leaked"

    edc_run = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs",
        data=json.dumps(
            {
                "operation_version_id": operation_version_id,
                "source_mode": "edc_import",
                "source_reference": "OPENCLINICA-001",
                "subject_identifier": "SUBJ-003",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
        HTTP_X_USER_ID="manager-1",
    )
    assert edc_run.status_code == 201
    assert edc_run.json()["source_mode"] == "edc_import"
