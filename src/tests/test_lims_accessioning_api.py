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


def _create_reference_bundle(client: Client, host: str) -> tuple[str, str, str]:
    created_lab = client.post(
        "/api/v1/lims/reference/labs",
        data=json.dumps({"name": "Central Lab", "code": "LAB-001"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert created_lab.status_code == 201
    lab_id = created_lab.json()["id"]

    created_study = client.post(
        "/api/v1/lims/reference/studies",
        data=json.dumps(
            {"name": "DBS Pilot", "code": "STUDY-001", "lead_lab_id": lab_id}
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert created_study.status_code == 201
    study_id = created_study.json()["id"]

    created_site = client.post(
        "/api/v1/lims/reference/sites",
        data=json.dumps(
            {
                "name": "Moshi Site",
                "code": "SITE-001",
                "study_id": study_id,
                "lab_id": lab_id,
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert created_site.status_code == 201
    return lab_id, study_id, created_site.json()["id"]


def _create_sample_type(client: Client, host: str) -> str:
    sample_type = client.post(
        "/api/v1/lims/biospecimen-types",
        data=json.dumps(
            {
                "name": "Dried Blood Spot",
                "key": "dbs",
                "identifier_prefix": "DBS",
                "barcode_prefix": "DBSB",
                "sequence_padding": 5,
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert sample_type.status_code == 201
    return sample_type.json()["id"]


def _bind_sample_type_metadata_schema(client: Client, host: str) -> None:
    schema = client.post(
        "/api/v1/lims/metadata/schemas",
        data=json.dumps(
            {
                "name": "DBS receiving",
                "code": "dbs-receiving",
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

    version = client.put(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions/{version_id}",
        data=json.dumps(
            {
                "fields": [
                    {
                        "name": "Tube count",
                        "field_key": "tube_count",
                        "field_type": "integer",
                        "required": True,
                    }
                ]
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert version.status_code == 200

    published = client.post(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions/{version_id}/publish",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert published.status_code == 200

    binding = client.post(
        "/api/v1/lims/metadata/bindings",
        data=json.dumps(
            {
                "schema_version_id": version_id,
                "target_type": "sample_type",
                "target_key": "dbs",
                "target_label": "DBS",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert binding.status_code == 201


@pytest.mark.django_db(transaction=True)
def test_lims_accessioning_supports_single_receive_with_metadata_validation(
    monkeypatch,
):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-accessioning-single")
    lab_id, study_id, site_id = _create_reference_bundle(client, host)
    sample_type_id = _create_sample_type(client, host)
    _bind_sample_type_metadata_schema(client, host)

    denied = client.post(
        "/api/v1/lims/accessioning/receive-single",
        data=json.dumps({"sample_type_id": sample_type_id}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert denied.status_code == 403

    invalid = client.post(
        "/api/v1/lims/accessioning/receive-single",
        data=json.dumps(
            {
                "sample_type_id": sample_type_id,
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "subject_identifier": "SUBJ-001",
                "quantity": "1.0",
                "quantity_unit": "mL",
                "metadata": {"tube_count": "bad"},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"] == "metadata_invalid"

    received = client.post(
        "/api/v1/lims/accessioning/receive-single",
        data=json.dumps(
            {
                "sample_type_id": sample_type_id,
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "subject_identifier": "SUBJ-001",
                "quantity": "1.0",
                "quantity_unit": "mL",
                "scan_value": "DBSB-00001",
                "barcode": "DBSB-00001",
                "received_at": "2026-03-18",
                "metadata": {"tube_count": 2},
                "receipt_context": {
                    "brought_by": "Courier Alpha",
                    "qc": {"decision": "accept", "notes": "visual QC ok"},
                    "storage": {"location": "Freezer A", "position": "A3"},
                },
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert received.status_code == 201
    assert received.json()["biospecimen"]["status"] == "received"
    assert received.json()["biospecimen"]["metadata"]["tube_count"] == 2
    assert received.json()["biospecimen"]["received_at"].startswith(
        "2026-03-18T00:00:00"
    )
    assert (
        received.json()["event"]["metadata"]["receipt_context"]["qc"]["decision"]
        == "accept"
    )
    assert (
        received.json()["event"]["metadata"]["receipt_context"]["brought_by"]
        == "Courier Alpha"
    )
    assert (
        received.json()["event"]["metadata"]["receipt_context"]["storage"]["location"]
        == "Freezer A"
    )
    assert received.json()["event"]["kind"] == "single"
    assert received.json()["operation_run"]["operation_code"] == "sample-accession"
    assert received.json()["operation_run"]["source_mode"] == "single"
    assert received.json()["operation_run"]["status"] == "completed"
    assert received.json()["qc_result"]["decision"] == "accept"
    assert received.json()["qc_result"]["notes"] == "visual QC ok"
    assert received.json()["discrepancy"] is None
    qc_task = next(
        item
        for item in received.json()["operation_run"]["tasks"]
        if item["node_key"] == "qc_decision"
    )
    assert qc_task["submissions"][0]["payload"]["qc_notes"] == "visual QC ok"
    assert qc_task["approvals"][0]["approved_by"] == ""
    intake_task = next(
        item
        for item in received.json()["operation_run"]["tasks"]
        if item["node_key"] == "intake_capture"
    )
    assert intake_task["submissions"][0]["payload"]["received_at"].startswith(
        "2026-03-18"
    )
    assert any(
        item["action"] == "bound"
        and item["receiving_event_id"] == received.json()["event"]["id"]
        for item in received.json()["operation_run"]["material_usages"]
    )


@pytest.mark.django_db(transaction=True)
def test_lims_accessioning_single_reject_creates_governed_operation_run(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-accessioning-single-reject")
    lab_id, study_id, site_id = _create_reference_bundle(client, host)
    sample_type_id = _create_sample_type(client, host)
    _bind_sample_type_metadata_schema(client, host)

    rejected = client.post(
        "/api/v1/lims/accessioning/receive-single",
        data=json.dumps(
            {
                "sample_type_id": sample_type_id,
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "subject_identifier": "SUBJ-REJECT-001",
                "quantity": "1.0",
                "quantity_unit": "mL",
                "received_at": "2026-03-18",
                "metadata": {"tube_count": 1},
                "receipt_context": {
                    "brought_by": "Courier Alpha",
                    "qc": {
                        "decision": "reject",
                        "notes": "tube leaked",
                        "rejection_code": "other",
                    },
                },
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert rejected.status_code == 201
    assert rejected.json()["biospecimen"] is None
    assert rejected.json()["event"] is None
    assert rejected.json()["operation_run"]["operation_code"] == "sample-accession"
    assert rejected.json()["operation_run"]["status"] == "rejected"
    assert rejected.json()["qc_result"]["decision"] == "reject"
    assert rejected.json()["discrepancy"]["status"] == "open"
    assert rejected.json()["discrepancy"]["notes"] == "tube leaked"
    qc_task = next(
        item
        for item in rejected.json()["operation_run"]["tasks"]
        if item["node_key"] == "qc_decision"
    )
    assert qc_task["submissions"][0]["payload"]["qc_notes"] == "tube leaked"
    assert qc_task["approvals"][0]["approved_by"] == ""
    assert not any(
        item["node_key"] == "storage_logging"
        for item in rejected.json()["operation_run"]["tasks"]
    )


@pytest.mark.django_db(transaction=True)
def test_lims_accessioning_supports_manifest_receive_discrepancies_and_reports(
    monkeypatch,
):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-accessioning-manifest")
    lab_id, study_id, site_id = _create_reference_bundle(client, host)
    sample_type_id = _create_sample_type(client, host)

    manifest = client.post(
        "/api/v1/lims/accessioning/manifests",
        data=json.dumps(
            {
                "sample_type_id": sample_type_id,
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "source_system": "courier-upload",
                "source_reference": "BATCH-001",
                "submit": True,
                "items": [
                    {
                        "position": 1,
                        "expected_subject_identifier": "SUBJ-001",
                        "expected_sample_identifier": "EXT-001",
                        "expected_barcode": "SCAN-001",
                        "quantity": "1.0",
                    },
                    {
                        "position": 2,
                        "expected_subject_identifier": "SUBJ-002",
                        "expected_sample_identifier": "EXT-002",
                        "expected_barcode": "SCAN-002",
                        "quantity": "1.0",
                    },
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert manifest.status_code == 201
    assert manifest.json()["status"] == "submitted"
    manifest_id = manifest.json()["id"]

    detail = client.get(
        f"/api/v1/lims/accessioning/manifests/{manifest_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert detail.status_code == 200
    first_item_id = detail.json()["items"][0]["id"]
    second_item_id = detail.json()["items"][1]["id"]

    scan_mismatch = client.post(
        f"/api/v1/lims/accessioning/manifests/{manifest_id}/items/{first_item_id}/receive",
        data=json.dumps({"scan_value": "WRONG"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert scan_mismatch.status_code == 400
    assert scan_mismatch.json()["error"] == "scan_mismatch"

    received = client.post(
        f"/api/v1/lims/accessioning/manifests/{manifest_id}/items/{first_item_id}/receive",
        data=json.dumps(
            {
                "scan_value": "SCAN-001",
                "notes": "arrived chilled",
                "received_at": "2026-03-19",
                "metadata": {"tube_count": 2},
                "receipt_context": {
                    "brought_by": "Site runner",
                    "qc": {"decision": "accept", "notes": "visual QC ok"},
                    "storage": {"location": "Freezer A", "position": "A3"},
                },
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert received.status_code == 200
    assert received.json()["item"]["status"] == "received"
    assert received.json()["item"]["received_at"].startswith("2026-03-19T00:00:00")
    assert (
        received.json()["event"]["metadata"]["receipt_context"]["brought_by"]
        == "Site runner"
    )
    assert (
        received.json()["event"]["metadata"]["receipt_context"]["storage"]["location"]
        == "Freezer A"
    )
    assert received.json()["event"]["kind"] == "manifest_item"
    assert received.json()["operation_run"]["operation_code"] == "sample-accession"
    assert received.json()["operation_run"]["source_mode"] == "batch"
    assert received.json()["operation_run"]["status"] == "completed"
    assert received.json()["qc_result"]["decision"] == "accept"
    assert received.json()["qc_result"]["notes"] == "visual QC ok"
    assert received.json()["discrepancy"] is None
    qc_task = next(
        item
        for item in received.json()["operation_run"]["tasks"]
        if item["node_key"] == "qc_decision"
    )
    assert qc_task["submissions"][0]["payload"]["qc_notes"] == "visual QC ok"
    intake_task = next(
        item
        for item in received.json()["operation_run"]["tasks"]
        if item["node_key"] == "intake_capture"
    )
    assert intake_task["submissions"][0]["payload"]["received_at"].startswith(
        "2026-03-19"
    )
    assert any(
        item["action"] == "bound"
        and item["receiving_event_id"] == received.json()["event"]["id"]
        for item in received.json()["operation_run"]["material_usages"]
    )

    discrepancy = client.post(
        "/api/v1/lims/receiving/discrepancies",
        data=json.dumps(
            {
                "manifest_id": manifest_id,
                "manifest_item_id": second_item_id,
                "code": "missing_sample",
                "notes": "package had only one card",
                "expected_data": {"expected_barcode": "SCAN-002"},
                "actual_data": {"observed_count": 1},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert discrepancy.status_code == 201
    assert discrepancy.json()["status"] == "open"

    report = client.get(
        f"/api/v1/lims/accessioning/manifests/{manifest_id}/report",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert report.status_code == 200
    assert report.json()["summary"]["total_items"] == 2
    assert report.json()["summary"]["received_items"] == 1
    assert report.json()["summary"]["discrepant_items"] == 1
    assert report.json()["summary"]["open_discrepancies"] == 1


@pytest.mark.django_db(transaction=True)
def test_lims_accessioning_manifest_reject_path_uses_governed_operation_runtime(
    monkeypatch,
):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-accessioning-manifest-reject")
    lab_id, study_id, site_id = _create_reference_bundle(client, host)
    sample_type_id = _create_sample_type(client, host)

    manifest = client.post(
        "/api/v1/lims/accessioning/manifests",
        data=json.dumps(
            {
                "sample_type_id": sample_type_id,
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "source_system": "edc-import",
                "source_reference": "OPENCLINICA-001",
                "submit": True,
                "items": [
                    {
                        "position": 1,
                        "expected_subject_identifier": "SUBJ-003",
                        "expected_sample_identifier": "EXT-003",
                        "expected_barcode": "SCAN-003",
                        "quantity": "1.0",
                        "metadata": {"tube_count": 1},
                    }
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert manifest.status_code == 201
    manifest_id = manifest.json()["id"]
    detail = client.get(
        f"/api/v1/lims/accessioning/manifests/{manifest_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert detail.status_code == 200
    item_id = detail.json()["items"][0]["id"]

    rejected = client.post(
        f"/api/v1/lims/accessioning/manifests/{manifest_id}/items/{item_id}/receive",
        data=json.dumps(
            {
                "source_mode": "edc_import",
                "source_reference": "OPENCLINICA-001",
                "received_at": "2026-03-19",
                "metadata": {"tube_count": 1},
                "receipt_context": {
                    "brought_by": "EDC import",
                    "qc": {
                        "decision": "reject",
                        "notes": "sample missing from shipment",
                        "rejection_code": "missing_sample",
                    },
                },
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert rejected.status_code == 200
    assert rejected.json()["item"]["status"] == "discrepant"
    assert rejected.json()["event"] is None
    assert rejected.json()["operation_run"]["operation_code"] == "sample-accession"
    assert rejected.json()["operation_run"]["source_mode"] == "edc_import"
    assert rejected.json()["operation_run"]["status"] == "rejected"
    assert rejected.json()["qc_result"]["decision"] == "reject"
    assert rejected.json()["qc_result"]["notes"] == "sample missing from shipment"
    assert rejected.json()["discrepancy"]["code"] == "missing_sample"
    qc_task = next(
        item
        for item in rejected.json()["operation_run"]["tasks"]
        if item["node_key"] == "qc_decision"
    )
    assert (
        qc_task["submissions"][0]["payload"]["qc_notes"]
        == "sample missing from shipment"
    )
    assert qc_task["submissions"][0]["payload"]["rejection_code"] == "missing_sample"
    assert qc_task["approvals"][0]["approved_by"] == ""
    assert not any(
        item["node_key"] == "storage_logging"
        for item in rejected.json()["operation_run"]["tasks"]
    )
