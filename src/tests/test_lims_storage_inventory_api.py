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
    response = client.post(
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
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.django_db(transaction=True)
def test_lims_storage_locations_and_biospecimen_history(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-storage")
    lab_id, study_id, site_id = _create_reference_bundle(client, host)
    sample_type_id = _create_sample_type(client, host)

    specimen = client.post(
        "/api/v1/lims/biospecimens",
        data=json.dumps(
            {
                "sample_type_id": sample_type_id,
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "subject_identifier": "SUBJ-001",
                "quantity": "3.0",
                "quantity_unit": "mL",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert specimen.status_code == 201
    specimen_id = specimen.json()["id"]

    facility = client.post(
        "/api/v1/lims/storage/locations",
        data=json.dumps({"lab_id": lab_id, "name": "Main Freezer Room", "code": "freezer-room", "level": "facility"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert facility.status_code == 201
    facility_id = facility.json()["id"]

    freezer = client.post(
        "/api/v1/lims/storage/locations",
        data=json.dumps(
            {
                "lab_id": lab_id,
                "parent_id": facility_id,
                "name": "Freezer A",
                "code": "freezer-a",
                "level": "equipment",
                "temperature_zone": "freezer_minus80",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert freezer.status_code == 201

    position = client.post(
        "/api/v1/lims/storage/locations",
        data=json.dumps(
            {
                "lab_id": lab_id,
                "parent_id": freezer.json()["id"],
                "name": "Rack 1 / Box 2 / A1",
                "code": "rack1-box2-a1",
                "level": "position",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert position.status_code == 201
    position_id = position.json()["id"]

    second_position = client.post(
        "/api/v1/lims/storage/locations",
        data=json.dumps(
            {
                "lab_id": lab_id,
                "parent_id": freezer.json()["id"],
                "name": "Rack 1 / Box 2 / A2",
                "code": "rack1-box2-a2",
                "level": "position",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert second_position.status_code == 201

    placed = client.post(
        f"/api/v1/lims/biospecimens/{specimen_id}/storage-records",
        data=json.dumps({"location_id": position_id, "reason": "placed", "notes": "initial placement"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
        HTTP_X_USER_ID="manager-1",
    )
    assert placed.status_code == 201
    assert placed.json()["location"]["id"] == position_id
    assert placed.json()["previous_location_id"] is None

    moved = client.post(
        f"/api/v1/lims/biospecimens/{specimen_id}/storage-records",
        data=json.dumps({"location_id": second_position.json()["id"], "reason": "moved", "notes": "move to adjacent slot"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
        HTTP_X_USER_ID="manager-1",
    )
    assert moved.status_code == 201
    assert moved.json()["previous_location_id"] == position_id

    history = client.get(
        f"/api/v1/lims/biospecimens/{specimen_id}/storage-records",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert history.status_code == 200
    assert len(history.json()["items"]) == 2
    assert history.json()["items"][0]["reason"] == "moved"

    detail = client.get(
        f"/api/v1/lims/biospecimens/{specimen_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert detail.status_code == 200
    assert detail.json()["current_storage_location_id"] == second_position.json()["id"]


@pytest.mark.django_db(transaction=True)
def test_lims_inventory_lots_and_transactions_track_consumable_usage(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-inventory")
    lab_id, study_id, site_id = _create_reference_bundle(client, host)
    sample_type_id = _create_sample_type(client, host)

    specimen = client.post(
        "/api/v1/lims/biospecimens",
        data=json.dumps(
            {
                "sample_type_id": sample_type_id,
                "study_id": study_id,
                "site_id": site_id,
                "lab_id": lab_id,
                "subject_identifier": "SUBJ-002",
                "quantity": "1.0",
                "quantity_unit": "mL",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert specimen.status_code == 201
    specimen_id = specimen.json()["id"]

    facility = client.post(
        "/api/v1/lims/storage/locations",
        data=json.dumps({"lab_id": lab_id, "name": "Consumables Store", "code": "consumables-store", "level": "facility"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert facility.status_code == 201

    shelf = client.post(
        "/api/v1/lims/storage/locations",
        data=json.dumps(
            {
                "lab_id": lab_id,
                "parent_id": facility.json()["id"],
                "name": "Shelf A",
                "code": "shelf-a",
                "level": "container",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert shelf.status_code == 201
    shelf_id = shelf.json()["id"]

    material = client.post(
        "/api/v1/lims/inventory/materials",
        data=json.dumps(
            {
                "name": "Extraction Reagent",
                "code": "extraction-reagent",
                "category": "reagent",
                "default_unit": "mL",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert material.status_code == 201

    lot = client.post(
        "/api/v1/lims/inventory/lots",
        data=json.dumps(
            {
                "material_id": material.json()["id"],
                "lab_id": lab_id,
                "storage_location_id": shelf_id,
                "lot_number": "LOT-001",
                "received_quantity": "100.0",
                "unit_of_measure": "mL",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
        HTTP_X_USER_ID="manager-2",
    )
    assert lot.status_code == 201
    lot_id = lot.json()["lot"]["id"]
    assert lot.json()["initial_transaction"]["transaction_type"] == "receipt"
    assert lot.json()["lot"]["on_hand_quantity"] == "100.000"

    consumed = client.post(
        f"/api/v1/lims/inventory/lots/{lot_id}/transactions",
        data=json.dumps(
            {
                "transaction_type": "consumption",
                "quantity_delta": "-5.0",
                "location_id": shelf_id,
                "biospecimen_id": specimen_id,
                "notes": "used for extraction prep",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
        HTTP_X_USER_ID="manager-2",
    )
    assert consumed.status_code == 201
    assert consumed.json()["biospecimen_id"] == specimen_id
    assert consumed.json()["resulting_quantity"] == "95.000"

    transactions = client.get(
        f"/api/v1/lims/inventory/lots/{lot_id}/transactions",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert transactions.status_code == 200
    assert len(transactions.json()["items"]) == 2
    assert transactions.json()["items"][0]["transaction_type"] == "consumption"

    lot_detail = client.get(
        f"/api/v1/lims/inventory/lots/{lot_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert lot_detail.status_code == 200
    assert lot_detail.json()["on_hand_quantity"] == "95.000"
