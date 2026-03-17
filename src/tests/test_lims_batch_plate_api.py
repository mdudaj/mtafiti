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
        data=json.dumps({"name": "DBS Pilot", "code": "STUDY-001", "lead_lab_id": lab_id}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert created_study.status_code == 201
    study_id = created_study.json()["id"]

    created_site = client.post(
        "/api/v1/lims/reference/sites",
        data=json.dumps({"name": "Moshi Site", "code": "SITE-001", "study_id": study_id, "lab_id": lab_id}),
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


def _receive_specimen(
    client: Client,
    host: str,
    *,
    sample_type_id: str,
    study_id: str,
    site_id: str,
    lab_id: str,
    subject_identifier: str,
    barcode: str,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/lims/accessioning/receive-single",
        data=json.dumps(
            {
                "sample_type_id": sample_type_id,
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "subject_identifier": subject_identifier,
                "quantity": "1.0",
                "quantity_unit": "mL",
                "barcode": barcode,
                "scan_value": barcode,
                "metadata": {},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert response.status_code == 201
    return response.json()["biospecimen"]


@pytest.mark.django_db(transaction=True)
def test_lims_plate_layouts_include_seeded_defaults(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-batch-layouts")

    response = client.get("/api/v1/lims/plate-layouts", HTTP_HOST=host, HTTP_X_USER_ROLES="lims.admin")
    assert response.status_code == 200
    keys = {item["key"] for item in response.json()["items"]}
    assert {"96-well", "384-well"}.issubset(keys)


@pytest.mark.django_db(transaction=True)
def test_lims_batch_plate_management_supports_assignments_and_worksheet_jobs(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-batch-management")
    lab_id, study_id, site_id = _create_reference_bundle(client, host)
    sample_type_id = _create_sample_type(client, host)

    layouts = client.get("/api/v1/lims/plate-layouts", HTTP_HOST=host, HTTP_X_USER_ROLES="lims.admin")
    assert layouts.status_code == 200
    layout_id = next(item["id"] for item in layouts.json()["items"] if item["key"] == "96-well")

    specimen_one = _receive_specimen(
        client,
        host,
        sample_type_id=sample_type_id,
        study_id=study_id,
        site_id=site_id,
        lab_id=lab_id,
        subject_identifier="SUBJ-001",
        barcode="DBSB-10001",
    )
    specimen_two = _receive_specimen(
        client,
        host,
        sample_type_id=sample_type_id,
        study_id=study_id,
        site_id=site_id,
        lab_id=lab_id,
        subject_identifier="SUBJ-002",
        barcode="DBSB-10002",
    )

    denied = client.post(
        "/api/v1/lims/processing-batches",
        data=json.dumps({"sample_type_id": sample_type_id}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert denied.status_code == 403

    created = client.post(
        "/api/v1/lims/processing-batches",
        data=json.dumps(
            {
                "sample_type_id": sample_type_id,
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "notes": "Batch for extraction worksheet",
                "metadata": {"workflow_stage": "extraction"},
                "plates": [
                    {
                        "layout_template_id": layout_id,
                        "label": "Extraction plate A",
                        "assignments": [
                            {
                                "biospecimen_id": specimen_one["id"],
                                "well_label": "A1",
                            },
                            {
                                "biospecimen_id": specimen_two["id"],
                                "position_index": 2,
                            },
                        ],
                    }
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    assert body["plate_count"] == 1
    assert body["assigned_specimen_count"] == 2
    assignments = body["plates"][0]["assignments"]
    assert [item["well_label"] for item in assignments] == ["A1", "A2"]
    batch_id = body["id"]

    duplicate = client.post(
        "/api/v1/lims/processing-batches",
        data=json.dumps(
            {
                "sample_type_id": sample_type_id,
                "plates": [
                    {
                        "layout_template_id": layout_id,
                        "assignments": [
                            {"biospecimen_id": specimen_one["id"], "well_label": "A1"},
                            {"biospecimen_id": specimen_one["id"], "well_label": "A2"},
                        ],
                    }
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["error"] == "duplicate_specimen_assignment"

    transitioned = client.post(
        f"/api/v1/lims/processing-batches/{batch_id}/transition",
        data=json.dumps({"status": "assigned"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert transitioned.status_code == 200
    assert transitioned.json()["status"] == "assigned"

    worksheet = client.get(
        f"/api/v1/lims/processing-batches/{batch_id}/worksheet",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert worksheet.status_code == 200
    worksheet_body = worksheet.json()
    assert worksheet_body["summary"]["plate_count"] == 1
    assert worksheet_body["summary"]["assigned_specimen_count"] == 2
    assert worksheet_body["plates"][0]["assignments"][1]["well_label"] == "A2"

    print_job = client.post(
        f"/api/v1/lims/processing-batches/{batch_id}/worksheet-print-job",
        data=json.dumps({"destination": "office-printer-1"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert print_job.status_code == 201
    print_body = print_job.json()
    assert print_body["batch"]["status"] == "printed"
    assert print_body["print_job"]["template_ref"] == "a4/batch-rows"
    preview = print_body["print_job"]["gateway_metadata"]["render_preview"]
    assert preview["label_count"] == 2
    assert preview["sheet_preset"] == "a4-38x21.2"
