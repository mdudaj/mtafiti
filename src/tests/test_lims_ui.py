import json
import uuid

import pytest
from django.test import Client
from django.urls import reverse
from django_tenants.utils import schema_context

from lims.models import (
    Country,
    District,
    Lab,
    Region,
    Site,
    Street,
    Study,
    TanzaniaAddressSyncRun,
    Ward,
)


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


def _provision_sample_accession_bundle(client: Client, host: str) -> tuple[str, str]:
    provisioned = client.post(
        "/api/v1/lims/reference/operations/sample-accession/provision",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert provisioned.status_code == 200
    payload = provisioned.json()
    return payload["operation_definition"]["id"], payload["operation_version"]["id"]


def _start_sample_accession_run(
    client: Client, host: str, *, operation_id: str, operation_version_id: str
) -> dict[str, object]:
    created = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs",
        data=json.dumps(
            {
                "operation_version_id": operation_version_id,
                "source_mode": "single",
                "subject_identifier": "SUBJ-UI-001",
                "external_identifier": "EXT-UI-001",
                "context": {"intake_mode": "bench"},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
        HTTP_X_USER_ID="manager-1",
    )
    assert created.status_code == 201
    return created.json()


@pytest.mark.django_db(transaction=True)
def test_lims_html_pages_render_with_role_aware_actions():
    client = Client()
    host = _create_lims_host(client, "tenant-ui")

    pages = [
        (reverse("lims_dashboard_page"), b"Laboratory operations workspace", None),
        (
            reverse("lims_task_inbox_page"),
            b"Workflow task inbox",
            b'data-lims-action="task-inbox"',
        ),
        (
            reverse("lims_reference_page"),
            b"Reference and geography",
            b"Choose a reference workflow",
        ),
        (
            reverse("lims_reference_sample_accession_page"),
            b"Sample accession reference bundle",
            b'data-lims-action="reference-sample-accession-provision"',
        ),
        (
            reverse("lims_reference_create_lab_page"),
            b"Create lab",
            b'data-lims-action="reference-lab-create"',
        ),
        (
            reverse("lims_reference_create_study_page"),
            b"Create study",
            b'data-lims-action="reference-study-create"',
        ),
        (
            reverse("lims_reference_create_site_page"),
            b"Create site",
            b'data-lims-action="reference-site-create"',
        ),
        (
            reverse("lims_reference_address_sync_page"),
            b"Run geography sync",
            b'data-lims-action="reference-address-sync"',
        ),
        (
            reverse("lims_metadata_page"),
            b"Metadata configuration",
            b"Choose a metadata workflow",
        ),
        (
            reverse("lims_metadata_create_vocabulary_page"),
            b"Create vocabulary",
            b'data-lims-action="metadata-vocabulary-create"',
        ),
        (
            reverse("lims_metadata_create_field_page"),
            b"Create field definition",
            b'data-lims-action="metadata-field-create"',
        ),
        (
            reverse("lims_metadata_create_schema_page"),
            b"Create form and draft version",
            b'data-lims-action="metadata-schema-create"',
        ),
        (
            reverse("lims_metadata_create_binding_page"),
            b"Create schema binding",
            b'data-lims-action="metadata-binding-create"',
        ),
        (
            reverse("lims_metadata_publish_version_page"),
            b"Publish schema version",
            b'data-lims-action="metadata-version-publish"',
        ),
        (
            reverse("lims_biospecimens_page"),
            b"Biospecimen registry",
            b'data-lims-action="biospecimen-create"',
        ),
        (
            reverse("lims_receiving_page"),
            b"Receiving and accessioning",
            b"Choose a receiving workflow",
        ),
        (
            reverse("lims_receiving_single_page"),
            b"Receive single specimen",
            b'data-lims-action="receiving-single-create"',
        ),
        (
            reverse("lims_receiving_batch_page"),
            b"Receive batch manifest",
            b'data-lims-action="receiving-manifest-create"',
        ),
        (
            reverse("lims_receiving_edc_import_page"),
            b"Retrieve metadata from EDC",
            b'data-lims-action="receiving-edc-import"',
        ),
        (
            reverse("lims_processing_page"),
            b"Batch and plate processing",
            b'data-lims-action="processing-batch-create"',
        ),
        (
            reverse("lims_storage_inventory_page"),
            b"Storage and inventory administration",
            b"Choose a storage or inventory workflow",
        ),
        (
            reverse("lims_storage_create_location_page"),
            b"Create storage location",
            b'data-lims-action="storage-location-create"',
        ),
        (
            reverse("lims_storage_create_placement_page"),
            b"Record specimen placement",
            b'data-lims-action="storage-placement-create"',
        ),
        (
            reverse("lims_storage_create_material_page"),
            b"Create inventory material",
            b'data-lims-action="inventory-material-create"',
        ),
        (
            reverse("lims_storage_create_lot_page"),
            b"Receive inventory lot",
            b'data-lims-action="inventory-lot-create"',
        ),
        (
            reverse("lims_storage_create_transaction_page"),
            b"Record stock transaction",
            b'data-lims-action="inventory-transaction-create"',
        ),
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

    response = client.get(
        reverse("lims_metadata_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )

    assert response.status_code == 200
    assert b"Metadata configuration" in response.content
    assert b"Choose a metadata workflow" not in response.content
    assert b"Open create vocabulary" not in response.content


@pytest.mark.django_db(transaction=True)
def test_metadata_page_shows_visual_schema_builder_for_admins():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-metadata-builder")

    response = client.get(
        reverse("lims_metadata_create_schema_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )

    assert response.status_code == 200
    assert b"Form metadata" in response.content
    assert b"Draft field builder" in response.content
    assert b"Add field to draft" in response.content
    assert b"Draft payload preview" in response.content
    assert b"Back to metadata" in response.content


@pytest.mark.django_db(transaction=True)
def test_reference_forms_expose_slug_and_address_selectors():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-reference-forms")

    lab_page = client.get(
        reverse("lims_reference_create_lab_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert lab_page.status_code == 200
    assert b"Auto-generated from lab name, but editable" in lab_page.content
    assert b"/api/v1/lims/reference/select-options?source=streets" in lab_page.content
    assert (
        b"document.querySelector('[data-lims-field=\"' + name + '\"]') || document.querySelector('[data-field=\"' + name + '\"]')"
        in lab_page.content
    )

    study_page = client.get(
        reverse("lims_reference_create_study_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert study_page.status_code == 200
    assert b"Auto-generated from study name, but editable" in study_page.content

    site_page = client.get(
        reverse("lims_reference_create_site_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert site_page.status_code == 200
    assert b"Auto-generated from site name, but editable" in site_page.content
    assert b"multiple size=" in site_page.content
    assert b"/api/v1/lims/reference/select-options?source=regions" in site_page.content
    assert (
        b"/api/v1/lims/reference/select-options?source=districts" in site_page.content
    )
    assert (
        b"/api/v1/lims/reference/select-options?source=wards" not in site_page.content
    )
    assert (
        b"/api/v1/lims/reference/select-options?source=streets" not in site_page.content
    )


@pytest.mark.django_db(transaction=True)
def test_reference_launchpad_renders_sample_accession_workflow_entry():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-reference-workflow-entry")
    reference_url = reverse("lims_reference_page")
    sample_accession_url = reverse("lims_reference_sample_accession_page")

    response = client.get(
        reference_url, HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin"
    )

    assert response.status_code == 200
    assert b"Provision sample accession" in response.content
    assert sample_accession_url.encode() in response.content


@pytest.mark.django_db(transaction=True)
def test_lims_launchpads_render_canonical_action_links():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-launchpad-action-links")
    task_inbox_url = reverse("lims_task_inbox_page")
    metadata_url = reverse("lims_metadata_page")
    receiving_url = reverse("lims_receiving_page")
    storage_url = reverse("lims_storage_inventory_page")
    sample_accession_url = reverse("lims_reference_sample_accession_page")
    metadata_vocabulary_url = reverse("lims_metadata_create_vocabulary_page")
    metadata_publish_url = reverse("lims_metadata_publish_version_page")
    receiving_single_url = reverse("lims_receiving_single_page")
    receiving_edc_import_url = reverse("lims_receiving_edc_import_page")
    storage_location_url = reverse("lims_storage_create_location_page")
    storage_transaction_url = reverse("lims_storage_create_transaction_page")

    task_inbox = client.get(
        task_inbox_url, HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin"
    )
    metadata = client.get(
        metadata_url, HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin"
    )
    receiving = client.get(
        receiving_url, HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin"
    )
    storage = client.get(storage_url, HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")

    assert task_inbox.status_code == 200
    assert receiving_url.encode() in task_inbox.content
    assert sample_accession_url.encode() in task_inbox.content

    assert metadata.status_code == 200
    assert metadata_vocabulary_url.encode() in metadata.content
    assert metadata_publish_url.encode() in metadata.content

    assert receiving.status_code == 200
    assert receiving_single_url.encode() in receiving.content
    assert receiving_edc_import_url.encode() in receiving.content

    assert storage.status_code == 200
    assert storage_location_url.encode() in storage.content
    assert storage_transaction_url.encode() in storage.content


@pytest.mark.django_db(transaction=True)
def test_lims_dashboard_renders_canonical_quick_links():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-dashboard-links")
    dashboard_url = reverse("lims_dashboard_page")
    reference_url = reverse("lims_reference_page")
    metadata_url = reverse("lims_metadata_page")
    processing_url = reverse("lims_processing_page")
    storage_url = reverse("lims_storage_inventory_page")

    response = client.get(
        dashboard_url, HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin"
    )

    assert response.status_code == 200
    assert reference_url.encode() in response.content
    assert metadata_url.encode() in response.content
    assert processing_url.encode() in response.content
    assert storage_url.encode() in response.content
    assert b"ready" in response.content


@pytest.mark.django_db(transaction=True)
def test_reference_launchpad_shows_site_study_badges_and_address_breadcrumbs():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-reference-launchpad")
    summary = client.get(
        "/api/v1/lims/summary", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin"
    )
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
        study_one = Study.objects.create(
            name="DBS Pilot", code="dbs-pilot", lead_lab=lab
        )
        study_two = Study.objects.create(
            name="DBS Extension", code="dbs-extension", lead_lab=lab
        )
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

    response = client.get(
        reverse("lims_reference_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )

    assert response.status_code == 200
    assert b"DBS Pilot" in response.content
    assert b"DBS Extension" in response.content
    assert b"lims-badge lims-badge--info" in response.content
    assert (
        b"Majengo market / Sokoine Road / Majengo / Moshi / Kilimanjaro / Tanzania / 25112"
        in response.content
    )
    assert (
        b"Clocktower / Sokoine Road / Majengo / Moshi / Kilimanjaro / Tanzania / 25112"
        in response.content
    )


@pytest.mark.django_db(transaction=True)
def test_address_sync_page_shows_live_progress_monitor():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-sync-progress")

    response = client.get(
        reverse("lims_reference_address_sync_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )

    assert response.status_code == 200
    assert b"Current progress" in response.content
    assert b"Discovered workload" in response.content
    assert b"Progress is based on pages discovered so far" in response.content
    assert b"data-sync-runs-table" in response.content
    assert b"data-sync-progress-bar" in response.content


@pytest.mark.django_db(transaction=True)
def test_reference_page_shows_live_sync_progress_and_active_run_marker():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-reference-sync")
    summary = client.get(
        "/api/v1/lims/summary", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin"
    )
    schema_name = summary.json()["tenant_schema"]

    with schema_context(schema_name):
        TanzaniaAddressSyncRun.objects.create(
            status=TanzaniaAddressSyncRun.Status.RUNNING,
            pages_processed=7,
            checkpoint={"queue": [{"path": "/next"}]},
            stats={"failure_count": 2},
        )

    response = client.get(
        reverse("lims_reference_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )

    assert response.status_code == 200
    assert b"Recent address sync runs" in response.content
    assert b"Progress updates automatically while a run is active" in response.content
    assert b"data-reference-sync-runs-table" in response.content
    assert b"Progress" in response.content
    assert b"Active run" in response.content
    assert b"lims-badge lims-badge--active" in response.content


@pytest.mark.django_db(transaction=True)
def test_reference_sample_accession_page_shows_bundle_status_after_provision():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-reference-sample-accession")

    initial = client.get(
        reverse("lims_reference_sample_accession_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert initial.status_code == 200
    assert b"Not provisioned" in initial.content
    assert b"Governed runs" in initial.content

    provisioned = client.post(
        "/api/v1/lims/reference/operations/sample-accession/provision",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert provisioned.status_code == 200

    page = client.get(
        reverse("lims_reference_sample_accession_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert page.status_code == 200
    assert b"Published v1" in page.content
    assert b"sample-accession-package" in page.content
    assert b"single, batch, edc_import" in page.content


@pytest.mark.django_db(transaction=True)
def test_task_inbox_lists_actionable_operator_work_and_links_to_runtime_detail(
    monkeypatch,
):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-ui-task-inbox")
    operation_id, operation_version_id = _provision_sample_accession_bundle(
        client, host
    )
    run = _start_sample_accession_run(
        client,
        host,
        operation_id=operation_id,
        operation_version_id=operation_version_id,
    )
    intake_task = next(
        item for item in run["tasks"] if item["node_key"] == "intake_capture"
    )
    task_detail_url = reverse(
        "lims_task_detail_page",
        kwargs={
            "operation_id": operation_id,
            "run_id": run["id"],
            "task_id": intake_task["id"],
        },
    )

    inbox = client.get(
        reverse("lims_task_inbox_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )

    assert inbox.status_code == 200
    assert b"Workflow task inbox" in inbox.content
    assert b"Intake capture" in inbox.content
    assert b"SUBJ-UI-001" in inbox.content
    assert task_detail_url.encode() in inbox.content

    detail = client.get(
        task_detail_url,
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )

    assert detail.status_code == 200
    assert b"Submit runtime payload" in detail.content
    assert b"/api/v1/lims/operations/" in detail.content
    assert b"Open receiving single surface" in detail.content


@pytest.mark.django_db(transaction=True)
def test_task_inbox_shows_approval_queue_for_review_roles(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-ui-task-approvals")
    operation_id, operation_version_id = _provision_sample_accession_bundle(
        client, host
    )
    run = _start_sample_accession_run(
        client,
        host,
        operation_id=operation_id,
        operation_version_id=operation_version_id,
    )
    intake_task = next(
        item for item in run["tasks"] if item["node_key"] == "intake_capture"
    )

    intake_submitted = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{run['id']}/tasks/{intake_task['id']}/submit",
        data=json.dumps(
            {
                "payload": {
                    "subject_identifier": "SUBJ-UI-001",
                    "received_at": "2026-03-21",
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
    qc_task_detail_url = reverse(
        "lims_task_detail_page",
        kwargs={
            "operation_id": operation_id,
            "run_id": run["id"],
            "task_id": qc_task["id"],
        },
    )

    qc_submitted = client.post(
        f"/api/v1/lims/operations/{operation_id}/runs/{run['id']}/tasks/{qc_task['id']}/submit",
        data=json.dumps(
            {"payload": {"qc_decision": "accept", "qc_notes": "Looks good"}}
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
        HTTP_X_USER_ID="operator-1",
    )
    assert qc_submitted.status_code == 200

    inbox = client.get(
        reverse("lims_task_inbox_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.qa",
        HTTP_X_USER_ID="qa-1",
    )

    assert inbox.status_code == 200
    assert b"Approval queue" in inbox.content
    assert b"QC decision" in inbox.content
    assert qc_task_detail_url.encode() in inbox.content

    detail = client.get(
        qc_task_detail_url,
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.qa",
        HTTP_X_USER_ID="qa-1",
    )

    assert detail.status_code == 200
    assert b"Approve or reopen task" in detail.content
    assert b"Submit approval" in detail.content
    assert b"Runtime approval endpoint" in detail.content


@pytest.mark.django_db(transaction=True)
def test_lims_feedback_banner_uses_message_and_status_flag():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-feedback")

    success = client.get(
        reverse("lims_reference_address_sync_page")
        + "?ui_message=Sync%20started&ui_error=0",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert success.status_code == 200
    assert b"Sync started" in success.content
    assert b"banner ok" in success.content
    assert b"check_circle" in success.content
    assert b'<span class="banner-message">Sync started</span>' in success.content

    failure = client.get(
        reverse("lims_reference_address_sync_page")
        + "?ui_message=Sync%20failed&ui_error=1",
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

    single_page = client.get(
        reverse("lims_receiving_single_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert single_page.status_code == 200
    assert b"Step 1 of 3" in single_page.content
    assert b"Receiving date" in single_page.content
    assert b"Brought by" in single_page.content
    assert b"Configured metadata" in single_page.content
    assert b"Configured storage" in single_page.content

    batch_page = client.get(
        reverse("lims_receiving_batch_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert batch_page.status_code == 200
    assert b"Download CSV template" in batch_page.content
    assert b"Import CSV / Excel-saved CSV" in batch_page.content
    assert b"Import batch receipt" in batch_page.content
    assert b"receiving_date" in batch_page.content
    assert b"brought_by" in batch_page.content

    edc_page = client.get(
        reverse("lims_receiving_edc_import_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert edc_page.status_code == 200
    assert b"Lab form" in edc_page.content
    assert b"Expected sample" in edc_page.content
    assert b"External ID to import" in edc_page.content
    assert b"Receiving date" in edc_page.content
    assert b"Brought by" in edc_page.content


@pytest.mark.django_db(transaction=True)
def test_storage_inventory_pages_show_admin_forms():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-storage")

    launchpad = client.get(
        reverse("lims_storage_inventory_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert launchpad.status_code == 200
    assert b"Storage and inventory administration" in launchpad.content
    assert b"Create storage location" in launchpad.content
    assert b"Record stock transaction" in launchpad.content

    location_page = client.get(
        reverse("lims_storage_create_location_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert location_page.status_code == 200
    assert b"Temperature zone" in location_page.content
    assert b"Metadata JSON" in location_page.content

    placement_page = client.get(
        reverse("lims_storage_create_placement_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert placement_page.status_code == 200
    assert b"Immutable storage history" in placement_page.content
    assert b"Quantity snapshot" in placement_page.content

    material_page = client.get(
        reverse("lims_storage_create_material_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert material_page.status_code == 200
    assert b"Default unit" in material_page.content
    assert b"Create inventory material" in material_page.content

    lot_page = client.get(
        reverse("lims_storage_create_lot_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert lot_page.status_code == 200
    assert b"Lot number" in lot_page.content
    assert b"Initial quantity" in lot_page.content

    transaction_page = client.get(
        reverse("lims_storage_create_transaction_page"),
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert transaction_page.status_code == 200
    assert b"Transaction type" in transaction_page.content
    assert b"Linked biospecimen" in transaction_page.content
