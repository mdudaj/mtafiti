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


@pytest.mark.django_db(transaction=True)
def test_lims_biospecimens_support_type_creation_id_generation_transitions_and_aliquots(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-biospecimens")
    lab_id, study_id, site_id = _create_reference_bundle(client, host)

    denied = client.post(
        "/api/v1/lims/biospecimen-types",
        data=json.dumps({"name": "DBS", "key": "dbs"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert denied.status_code == 403

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
    sample_type_id = sample_type.json()["id"]

    specimen = client.post(
        "/api/v1/lims/biospecimens",
        data=json.dumps(
            {
                "sample_type_id": sample_type_id,
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "subject_identifier": "SUBJ-001",
                "quantity": "3.5",
                "quantity_unit": "mL",
                "metadata": {"tube_color": "purple"},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert specimen.status_code == 201
    specimen_payload = specimen.json()
    assert specimen_payload["sample_identifier"] == "DBS-00001"
    assert specimen_payload["barcode"] == "DBSB-00001"
    assert specimen_payload["status"] == "registered"

    invalid_transition = client.post(
        f"/api/v1/lims/biospecimens/{specimen_payload['id']}/transition",
        data=json.dumps({"status": "consumed"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.qa",
    )
    assert invalid_transition.status_code == 400
    assert invalid_transition.json()["error"] == "invalid_transition"

    received = client.post(
        f"/api/v1/lims/biospecimens/{specimen_payload['id']}/transition",
        data=json.dumps({"status": "received"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.qa",
    )
    assert received.status_code == 200
    assert received.json()["status"] == "received"

    available = client.post(
        f"/api/v1/lims/biospecimens/{specimen_payload['id']}/transition",
        data=json.dumps({"status": "available"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.qa",
    )
    assert available.status_code == 200
    assert available.json()["status"] == "available"

    aliquots = client.post(
        f"/api/v1/lims/biospecimens/{specimen_payload['id']}/aliquots",
        data=json.dumps({"count": 2, "quantity": "0.5", "quantity_unit": "mL"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert aliquots.status_code == 201
    aliquot_items = aliquots.json()["items"]
    assert len(aliquot_items) == 2
    assert aliquot_items[0]["kind"] == "aliquot"
    assert aliquot_items[0]["parent_specimen_id"] == specimen_payload["id"]
    assert aliquot_items[0]["lineage_root_id"] == specimen_payload["id"]

    detail = client.get(
        f"/api/v1/lims/biospecimens/{specimen_payload['id']}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "aliquoted"
    assert len(detail.json()["aliquot_ids"]) == 2


@pytest.mark.django_db(transaction=True)
def test_lims_biospecimen_pools_require_matching_types_and_mark_members_pooled(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-biospecimen-pools")
    lab_id, study_id, site_id = _create_reference_bundle(client, host)

    dbs = client.post(
        "/api/v1/lims/biospecimen-types",
        data=json.dumps({"name": "DBS", "key": "dbs", "identifier_prefix": "DBS", "barcode_prefix": "DBSB"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert dbs.status_code == 201
    plasma = client.post(
        "/api/v1/lims/biospecimen-types",
        data=json.dumps({"name": "Plasma", "key": "plasma", "identifier_prefix": "PL", "barcode_prefix": "PLB"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert plasma.status_code == 201

    def create_specimen(sample_type_id: str, subject_identifier: str) -> str:
        response = client.post(
            "/api/v1/lims/biospecimens",
            data=json.dumps(
                {
                    "sample_type_id": sample_type_id,
                    "study_id": study_id,
                    "site_id": site_id,
                    "lab_id": lab_id,
                    "subject_identifier": subject_identifier,
                    "quantity": "1.0",
                    "quantity_unit": "mL",
                }
            ),
            content_type="application/json",
            HTTP_HOST=host,
            HTTP_X_USER_ROLES="lims.admin",
        )
        assert response.status_code == 201
        specimen_id = response.json()["id"]
        received = client.post(
            f"/api/v1/lims/biospecimens/{specimen_id}/transition",
            data=json.dumps({"status": "received"}),
            content_type="application/json",
            HTTP_HOST=host,
            HTTP_X_USER_ROLES="lims.qa",
        )
        assert received.status_code == 200
        available = client.post(
            f"/api/v1/lims/biospecimens/{specimen_id}/transition",
            data=json.dumps({"status": "available"}),
            content_type="application/json",
            HTTP_HOST=host,
            HTTP_X_USER_ROLES="lims.qa",
        )
        assert available.status_code == 200
        return specimen_id

    specimen_one_id = create_specimen(dbs.json()["id"], "SUBJ-101")
    specimen_two_id = create_specimen(dbs.json()["id"], "SUBJ-102")
    mismatched_specimen_id = create_specimen(plasma.json()["id"], "SUBJ-999")

    mismatch = client.post(
        "/api/v1/lims/biospecimen-pools",
        data=json.dumps(
            {
                "sample_type_id": dbs.json()["id"],
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "specimen_ids": [specimen_one_id, mismatched_specimen_id],
                "quantity": "2.0",
                "quantity_unit": "mL",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["error"] == "sample_type_mismatch"

    pooled = client.post(
        "/api/v1/lims/biospecimen-pools",
        data=json.dumps(
            {
                "sample_type_id": dbs.json()["id"],
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "specimen_ids": [specimen_one_id, specimen_two_id],
                "quantity": "2.0",
                "quantity_unit": "mL",
                "metadata": {"strategy": "equal-volume"},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert pooled.status_code == 201
    pool_payload = pooled.json()
    assert pool_payload["pool_identifier"].startswith("DBS-POOL-")
    assert len(pool_payload["member_ids"]) == 2

    listed_pools = client.get(
        "/api/v1/lims/biospecimen-pools",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert listed_pools.status_code == 200
    assert listed_pools.json()["items"][0]["id"] == pool_payload["id"]

    specimen_one = client.get(
        f"/api/v1/lims/biospecimens/{specimen_one_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert specimen_one.status_code == 200
    assert specimen_one.json()["status"] == "pooled"
