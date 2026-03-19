import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from lims.models import Country, District, Lab, Region, Site, Street, Study, TanzaniaAddressSyncRun, Ward


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
def test_lims_html_pages_render_with_role_aware_actions():
    client = Client()
    host = _create_lims_host(client, "tenant-ui")

    pages = [
        ("/lims/", b"Laboratory operations workspace", None),
        ("/lims/reference/", b"Reference and geography", b"Choose a reference workflow"),
        ("/lims/reference/labs/create/", b"Create lab", b'data-lims-action="reference-lab-create"'),
        ("/lims/reference/studies/create/", b"Create study", b'data-lims-action="reference-study-create"'),
        ("/lims/reference/sites/create/", b"Create site", b'data-lims-action="reference-site-create"'),
        ("/lims/reference/address-sync/", b"Run geography sync", b'data-lims-action="reference-address-sync"'),
        ("/lims/metadata/", b"Metadata configuration", b"Choose a metadata workflow"),
        ("/lims/metadata/vocabularies/create/", b"Create vocabulary", b'data-lims-action="metadata-vocabulary-create"'),
        ("/lims/metadata/fields/create/", b"Create field definition", b'data-lims-action="metadata-field-create"'),
        ("/lims/metadata/schemas/create/", b"Create schema and first version", b'data-lims-action="metadata-schema-create"'),
        ("/lims/metadata/bindings/create/", b"Create schema binding", b'data-lims-action="metadata-binding-create"'),
        ("/lims/metadata/versions/publish/", b"Publish schema version", b'data-lims-action="metadata-version-publish"'),
        ("/lims/biospecimens/", b"Biospecimen registry", b'data-lims-action="biospecimen-create"'),
        ("/lims/receiving/", b"Receiving and accessioning", b"Choose a receiving workflow"),
        ("/lims/receiving/single/", b"Receive single specimen", b'data-lims-action="receiving-single-create"'),
        ("/lims/receiving/batch/", b"Receive batch manifest", b'data-lims-action="receiving-manifest-create"'),
        ("/lims/receiving/edc-import/", b"Retrieve metadata from EDC", b'data-lims-action="receiving-edc-import"'),
        ("/lims/processing/", b"Batch and plate processing", b'data-lims-action="processing-batch-create"'),
    ]

    for path, title, action_marker in pages:
        response = client.get(path, HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")
        assert response.status_code == 200
        assert title in response.content
        assert b"Dashboard" in response.content
        if action_marker:
            assert action_marker in response.content


@pytest.mark.django_db(transaction=True)
def test_lims_operator_can_view_metadata_page_without_manage_actions(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-ui-operator")

    response = client.get("/lims/metadata/", HTTP_HOST=host, HTTP_X_USER_ROLES="lims.operator")

    assert response.status_code == 200
    assert b"Metadata configuration" in response.content
    assert b"Choose a metadata workflow" not in response.content
    assert b"Open create vocabulary" not in response.content


@pytest.mark.django_db(transaction=True)
def test_metadata_page_shows_visual_schema_builder_for_admins():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-metadata-builder")

    response = client.get("/lims/metadata/schemas/create/", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")

    assert response.status_code == 200
    assert b"Visual schema builder" in response.content
    assert b"Add to designer" in response.content
    assert b"Schema payload preview" in response.content
    assert b"Back to metadata" in response.content


@pytest.mark.django_db(transaction=True)
def test_reference_forms_expose_slug_and_address_selectors():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-reference-forms")

    lab_page = client.get("/lims/reference/labs/create/", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")
    assert lab_page.status_code == 200
    assert b"Auto-generated from lab name, but editable" in lab_page.content
    assert b"/api/v1/lims/reference/select-options?source=streets" in lab_page.content
    assert b"document.querySelector('[data-lims-field=\"' + name + '\"]') || document.querySelector('[data-field=\"' + name + '\"]')" in lab_page.content

    study_page = client.get("/lims/reference/studies/create/", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")
    assert study_page.status_code == 200
    assert b"Auto-generated from study name, but editable" in study_page.content

    site_page = client.get("/lims/reference/sites/create/", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")
    assert site_page.status_code == 200
    assert b"Auto-generated from site name, but editable" in site_page.content
    assert b"multiple size=" in site_page.content
    assert b"/api/v1/lims/reference/select-options?source=regions" in site_page.content
    assert b"/api/v1/lims/reference/select-options?source=districts" in site_page.content
    assert b"/api/v1/lims/reference/select-options?source=wards" not in site_page.content
    assert b"/api/v1/lims/reference/select-options?source=streets" not in site_page.content


@pytest.mark.django_db(transaction=True)
def test_reference_launchpad_shows_site_study_badges_and_address_breadcrumbs():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-reference-launchpad")
    summary = client.get("/api/v1/lims/summary", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")
    schema_name = summary.json()["tenant_schema"]

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
        lab = Lab.objects.create(
            name="Central Lab",
            code="central-lab",
            address_line="Clocktower",
            country=country,
            region=region,
            district=district,
            ward=ward,
            street=street,
            postcode="25112",
        )
        study_one = Study.objects.create(name="DBS Pilot", code="dbs-pilot", lead_lab=lab)
        study_two = Study.objects.create(name="DBS Extension", code="dbs-extension", lead_lab=lab)
        site = Site.objects.create(
            name="Moshi Site",
            code="moshi-site",
            study=study_one,
            lab=lab,
            address_line="Majengo market",
            country=country,
            region=region,
            district=district,
            ward=ward,
            street=street,
            postcode="25112",
        )
        site.studies.set([study_one, study_two])

    response = client.get("/lims/reference/", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")

    assert response.status_code == 200
    assert b"DBS Pilot" in response.content
    assert b"DBS Extension" in response.content
    assert b"lims-badge lims-badge--info" in response.content
    assert b"Majengo market / Sokoine Road / Majengo / Moshi / Kilimanjaro / Tanzania / 25112" in response.content
    assert b"Clocktower / Sokoine Road / Majengo / Moshi / Kilimanjaro / Tanzania / 25112" in response.content


@pytest.mark.django_db(transaction=True)
def test_address_sync_page_shows_live_progress_monitor():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-sync-progress")

    response = client.get("/lims/reference/address-sync/", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")

    assert response.status_code == 200
    assert b"Current progress" in response.content
    assert b"Discovered workload" in response.content
    assert b"Progress is based on pages discovered so far" in response.content
    assert b'data-sync-runs-table' in response.content
    assert b'data-sync-progress-bar' in response.content


@pytest.mark.django_db(transaction=True)
def test_reference_page_shows_live_sync_progress_and_active_run_marker():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-reference-sync")
    summary = client.get("/api/v1/lims/summary", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")
    schema_name = summary.json()["tenant_schema"]

    with schema_context(schema_name):
        TanzaniaAddressSyncRun.objects.create(
            status=TanzaniaAddressSyncRun.Status.RUNNING,
            pages_processed=7,
            checkpoint={"queue": [{"path": "/next"}]},
            stats={"failure_count": 2},
        )

    response = client.get("/lims/reference/", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")

    assert response.status_code == 200
    assert b"Recent address sync runs" in response.content
    assert b"Progress updates automatically while a run is active" in response.content
    assert b'data-reference-sync-runs-table' in response.content
    assert b"Progress" in response.content
    assert b"Active run" in response.content
    assert b"lims-badge lims-badge--active" in response.content


@pytest.mark.django_db(transaction=True)
def test_lims_feedback_banner_uses_message_and_status_flag():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-feedback")

    success = client.get(
        "/lims/reference/address-sync/?ui_message=Sync%20started&ui_error=0",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert success.status_code == 200
    assert b"Sync started" in success.content
    assert b"banner ok" in success.content
    assert b"check_circle" in success.content
    assert b'<span class="banner-message">Sync started</span>' in success.content

    failure = client.get(
        "/lims/reference/address-sync/?ui_message=Sync%20failed&ui_error=1",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert failure.status_code == 200
    assert b"Sync failed" in failure.content
    assert b"banner err" in failure.content
    assert b"error" in failure.content
    assert b'<span class="banner-message">Sync failed</span>' in failure.content


@pytest.mark.django_db(transaction=True)
def test_receiving_pages_show_qc_storage_and_import_workflows():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-receiving")

    single_page = client.get("/lims/receiving/single/", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")
    assert single_page.status_code == 200
    assert b"Step 1 of 3" in single_page.content
    assert b"Receiving date" in single_page.content
    assert b"Brought by" in single_page.content
    assert b"Configured metadata" in single_page.content
    assert b"Configured storage" in single_page.content

    batch_page = client.get("/lims/receiving/batch/", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")
    assert batch_page.status_code == 200
    assert b"Download CSV template" in batch_page.content
    assert b"Import CSV / Excel-saved CSV" in batch_page.content
    assert b"Import batch receipt" in batch_page.content
    assert b"receiving_date" in batch_page.content
    assert b"brought_by" in batch_page.content

    edc_page = client.get("/lims/receiving/edc-import/", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")
    assert edc_page.status_code == 200
    assert b"Lab form" in edc_page.content
    assert b"Expected sample" in edc_page.content
    assert b"External ID to import" in edc_page.content
    assert b"Receiving date" in edc_page.content
    assert b"Brought by" in edc_page.content
