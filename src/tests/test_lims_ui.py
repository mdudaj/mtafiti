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


@pytest.mark.django_db(transaction=True)
def test_lims_html_pages_render_with_role_aware_actions():
    client = Client()
    host = _create_lims_host(client, "tenant-ui")

    pages = [
        ("/lims/", b"Laboratory operations workspace", None),
        ("/lims/reference/", b"Reference and geography", b'data-lims-action="reference-lab-create"'),
        ("/lims/metadata/", b"Metadata configuration", b'data-lims-action="metadata-schema-create"'),
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
    assert b'data-lims-action="metadata-schema-create"' not in response.content
    assert b'data-lims-action="metadata-vocabulary-create"' not in response.content


@pytest.mark.django_db(transaction=True)
def test_metadata_page_shows_visual_schema_builder_for_admins():
    client = Client()
    host = _create_lims_host(client, "tenant-ui-metadata-builder")

    response = client.get("/lims/metadata/", HTTP_HOST=host, HTTP_X_USER_ROLES="tenant.admin")

    assert response.status_code == 200
    assert b"Visual schema builder" in response.content
    assert b"Add to designer" in response.content
    assert b"Wizard step" in response.content
    assert b"Schema payload preview" in response.content


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
