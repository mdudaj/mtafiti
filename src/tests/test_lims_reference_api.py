import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from lims.models import Country, District, Lab, Postcode, Region, Site, Street, Study, Ward


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
def test_lims_reference_crud_and_select_options(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-reference")

    denied_create = client.post(
        "/api/v1/lims/reference/labs",
        data=json.dumps({"name": "Central Lab"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert denied_create.status_code == 403

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
    site_id = created_site.json()["id"]

    listed_labs = client.get(
        "/api/v1/lims/reference/labs",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert listed_labs.status_code == 200
    assert listed_labs.json()["items"][0]["name"] == "Central Lab"

    detail_site = client.get(
        f"/api/v1/lims/reference/sites/{site_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert detail_site.status_code == 200
    assert detail_site.json()["study_id"] == study_id

    updated_site = client.put(
        f"/api/v1/lims/reference/sites/{site_id}",
        data=json.dumps({"name": "Moshi Site", "code": "SITE-001", "study_id": study_id, "lab_id": lab_id}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert updated_site.status_code == 200
    assert updated_site.json()["code"] == "SITE-001"

    select_labs = client.get(
        "/api/v1/lims/reference/select-options?source=labs&q=central",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert select_labs.status_code == 200
    assert select_labs.json()["items"][0]["label"] == "Central Lab"


@pytest.mark.django_db(transaction=True)
def test_lims_reference_selectors_filter_address_hierarchy(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-address-selectors")
    schema_name = client.get("/api/v1/lims/summary", HTTP_HOST=host, HTTP_X_USER_ROLES="lims.admin").json()["tenant_schema"]

    with schema_context(schema_name):
        country = Country.objects.get(code="TZ")
        region = Region.objects.create(
            country=country,
            name="Kilimanjaro",
            slug="kilimanjaro",
            source_path="/kilimanjaro",
            source_url="https://www.tanzaniapostcode.com/kilimanjaro",
        )
        district = District.objects.create(
            region=region,
            name="Moshi",
            slug="moshi",
            source_path="/kilimanjaro/moshi",
            source_url="https://www.tanzaniapostcode.com/kilimanjaro/moshi",
        )
        ward = Ward.objects.create(
            district=district,
            name="Majengo",
            slug="majengo",
            source_path="/kilimanjaro/moshi/majengo",
            source_url="https://www.tanzaniapostcode.com/kilimanjaro/moshi/majengo",
        )
        street = Street.objects.create(
            ward=ward,
            name="Sokoine Road",
            slug="sokoine-road",
            source_path="/kilimanjaro/moshi/majengo/sokoine-road",
            source_url="https://www.tanzaniapostcode.com/kilimanjaro/moshi/majengo/sokoine-road",
        )
        postcode = Postcode.objects.create(
            street=street,
            code="25112",
            source_path="/kilimanjaro/moshi/majengo/sokoine-road",
            source_url="https://www.tanzaniapostcode.com/kilimanjaro/moshi/majengo/sokoine-road",
        )

    countries = client.get(
        "/api/v1/lims/reference/select-options?source=countries",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert countries.status_code == 200
    assert countries.json()["items"][0]["label"] == "Tanzania"

    regions = client.get(
        f"/api/v1/lims/reference/select-options?source=regions&country_id={country.id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert regions.status_code == 200
    assert regions.json()["items"][0]["label"] == "Kilimanjaro"

    districts = client.get(
        f"/api/v1/lims/reference/select-options?source=districts&region_id={region.id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert districts.status_code == 200
    assert districts.json()["items"][0]["label"] == "Moshi"

    wards = client.get(
        f"/api/v1/lims/reference/select-options?source=wards&district_id={district.id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert wards.status_code == 200
    assert wards.json()["items"][0]["label"] == "Majengo"

    streets = client.get(
        f"/api/v1/lims/reference/select-options?source=streets&ward_id={ward.id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert streets.status_code == 200
    assert streets.json()["items"][0]["label"] == "Sokoine Road"

    postcodes = client.get(
        f"/api/v1/lims/reference/select-options?source=postcodes&street_id={street.id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert postcodes.status_code == 200
    assert postcodes.json()["items"][0]["label"] == "25112"
