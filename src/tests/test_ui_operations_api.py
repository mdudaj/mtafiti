import json
import uuid

import pytest
from django.test import Client
from django.test.utils import override_settings
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


def _create_tenants():
    host_a = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    host_b = f"tenantb-{uuid.uuid4().hex[:6]}.example"
    with schema_context("public"):
        tenant_a = Tenant(
            schema_name=f"t_{uuid.uuid4().hex[:8]}",
            name=f"Tenant A {uuid.uuid4().hex[:6]}",
        )
        tenant_a.save()
        Domain(domain=host_a, tenant=tenant_a, is_primary=True).save()
        tenant_b = Tenant(
            schema_name=f"t_{uuid.uuid4().hex[:8]}",
            name=f"Tenant B {uuid.uuid4().hex[:6]}",
        )
        tenant_b.save()
        Domain(domain=host_b, tenant=tenant_b, is_primary=True).save()
    return host_a, host_b


@pytest.mark.django_db(transaction=True)
def test_ui_operations_dashboard_and_monitors():
    host, _ = _create_tenants()
    client = Client()
    project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "UI Ops Project"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    project_id = project.json()["id"]

    ingestion = client.post(
        "/api/v1/ingestions",
        data=json.dumps(
            {
                "project_id": project_id,
                "connector": "dbt",
                "source": {"processed_entities": 2},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    ingestion_id = ingestion.json()["id"]
    client.post(
        "/api/v1/connectors/runs",
        data=json.dumps({"ingestion_id": ingestion_id, "execution_path": "worker"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    workflow = client.post(
        "/api/v1/orchestration/workflows",
        data=json.dumps(
            {
                "name": "ui-orch",
                "project_id": project_id,
                "steps": [{"step_id": "s1", "ingestion_id": ingestion_id}],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    run = client.post(
        "/api/v1/orchestration/runs",
        data=json.dumps({"workflow_id": workflow.json()["id"]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    client.post(
        f"/api/v1/orchestration/runs/{run.json()['id']}/transition",
        data=json.dumps({"action": "start"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {"item_type": "quality_exception", "subject_ref": f"project:{project_id}"}
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    client.post(
        "/api/v1/agent/runs",
        data=json.dumps(
            {
                "prompt": f"project:{project_id} summarize failures",
                "allowed_tools": ["quality.read"],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )

    dashboard = client.get(
        f"/api/v1/ui/operations/dashboard?project_id={project_id}",
        HTTP_HOST=host,
    )
    assert dashboard.status_code == 200
    assert "cards" in dashboard.json()
    assert "stewardship" in dashboard.json()["cards"]
    assert "orchestration" in dashboard.json()["cards"]
    assert "agent" in dashboard.json()["cards"]

    workbench = client.get(
        "/api/v1/ui/operations/stewardship-workbench",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert workbench.status_code == 200
    assert len(workbench.json()["items"]) == 1
    assert "assign" in workbench.json()["items"][0]["allowed_actions"]

    orchestration_monitor = client.get(
        f"/api/v1/ui/operations/orchestration-monitor?project_id={project_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert orchestration_monitor.status_code == 200
    assert len(orchestration_monitor.json()["workflows"]) == 1
    assert len(orchestration_monitor.json()["runs"]) == 1

    agent_monitor = client.get(
        f"/api/v1/ui/operations/agent-monitor?project_id={project_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert agent_monitor.status_code == 200
    assert len(agent_monitor.json()["runs"]) == 1


@pytest.mark.django_db(transaction=True)
def test_ui_operations_are_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {"item_type": "quality_exception", "subject_ref": "asset:customers"}
        ),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    dashboard_a = client.get("/api/v1/ui/operations/dashboard", HTTP_HOST=host_a)
    dashboard_b = client.get("/api/v1/ui/operations/dashboard", HTTP_HOST=host_b)
    assert dashboard_a.status_code == 200
    assert dashboard_b.status_code == 200
    assert dashboard_a.json()["cards"]["stewardship"]["open"] == 1
    assert dashboard_b.json()["cards"]["stewardship"]["open"] == 0


@pytest.mark.django_db(transaction=True)
def test_ui_operations_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()

    denied = client.get("/api/v1/ui/operations/dashboard", HTTP_HOST=host)
    assert denied.status_code == 403

    allowed = client.get(
        "/api/v1/ui/operations/dashboard",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert allowed.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_ui_operations_html_pages_render():
    host, _ = _create_tenants()
    client = Client()

    project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "Ajax Filter Project", "code": "AJX-01"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    template = client.post(
        "/api/v1/printing/templates",
        data=json.dumps(
            {
                "name": "Searchable Template",
                "template_ref": "zebra/searchable",
                "output_format": "zpl",
                "content": "^XA^XZ",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert template.status_code == 201

    gateway = client.post(
        "/api/v1/printing/gateways",
        data=json.dumps(
            {
                "gateway_ref": "printer-search-01",
                "display_name": "Search Printer",
                "status": "online",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert gateway.status_code == 201

    dashboard = client.get("/ui/operations/dashboard", HTTP_HOST=host)
    stewardship = client.get(
        "/ui/operations/stewardship",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    orchestration = client.get(f"/ui/operations/orchestration?project_id={project_id}", HTTP_HOST=host)
    printing = client.get(
        "/ui/operations/printing",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor,tenant.admin",
    )
    agent = client.get(f"/ui/operations/agent?project_id={project_id}", HTTP_HOST=host)
    workspace = client.get("/app", HTTP_HOST=host)

    assert dashboard.status_code == 200
    assert stewardship.status_code == 200
    assert orchestration.status_code == 200
    assert printing.status_code == 200
    assert agent.status_code == 200
    assert workspace.status_code == 200
    assert b"Skip to content" in dashboard.content
    assert b"Operations Dashboard" in dashboard.content
    assert b"Stewardship Workbench" in stewardship.content
    assert b"Printing Operations" in printing.content
    assert b"data-ajax-model-select" in dashboard.content
    assert b"/api/v1/ui/model-select-options?source=projects" in dashboard.content
    assert b"/api/v1/ui/model-select-options?source=assets" in stewardship.content
    assert b"/api/v1/ui/model-select-options?source=print_templates" in printing.content
    assert b"/api/v1/ui/model-select-options?source=print_gateways" in printing.content
    assert b"/api/v1/ui/model-select-options?source=print_templates" in workspace.content
    assert b"/api/v1/ui/model-select-options?source=print_gateways" in workspace.content
    assert b"Ajax Filter Project" in orchestration.content
    assert b"Ajax Filter Project" in agent.content


@pytest.mark.django_db(transaction=True)
@override_settings(EDMP_UI_MATERIAL_ENABLED=True)
def test_ui_operations_html_pages_fallback_when_material_base_missing():
    host, _ = _create_tenants()
    client = Client()
    dashboard = client.get("/ui/operations/dashboard", HTTP_HOST=host)
    assert dashboard.status_code == 200
    assert b"Mtafiti Operations" in dashboard.content


@pytest.mark.django_db(transaction=True)
def test_ui_operations_html_filters_apply():
    host, _ = _create_tenants()
    client = Client()

    client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {"item_type": "quality_exception", "subject_ref": "asset:critical", "severity": "critical"}
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {"item_type": "quality_exception", "subject_ref": "asset:low", "severity": "low"}
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )

    filtered = client.get(
        "/ui/operations/stewardship?severity=critical",
        HTTP_HOST=host,
    )
    assert filtered.status_code == 200
    assert b"asset:critical" in filtered.content
    assert b"asset:low" not in filtered.content


@pytest.mark.django_db(transaction=True)
def test_ui_action_controls_visibility_by_role(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()

    client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {"item_type": "quality_exception", "subject_ref": "asset:role-check", "severity": "high"}
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )

    admin_view = client.get(
        "/ui/operations/stewardship",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    reader_view = client.get(
        "/ui/operations/stewardship",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )

    assert admin_view.status_code == 200
    assert reader_view.status_code == 200
    assert b'data-ui-action="stewardship"' in admin_view.content
    assert b'data-ui-action="stewardship"' not in reader_view.content


@pytest.mark.django_db(transaction=True)
def test_ui_feedback_banner_renders_from_query_params():
    host, _ = _create_tenants()
    client = Client()
    page = client.get(
        "/ui/operations/dashboard?ui_message=Action%20completed&ui_error=0",
        HTTP_HOST=host,
    )
    assert page.status_code == 200
    assert b"Action completed" in page.content
    assert b"banner ok" in page.content


@pytest.mark.django_db(transaction=True)
def test_stewardship_action_form_fields_render_for_managers(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()
    client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {"item_type": "quality_exception", "subject_ref": "asset:form", "severity": "high"}
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    page = client.get(
        "/ui/operations/stewardship",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert page.status_code == 200
    assert b'data-ui-action-form="stewardship"' in page.content
    assert b"assignee (for assign)" in page.content
    assert b"resolution JSON (for resolve)" in page.content


@pytest.mark.django_db(transaction=True)
def test_stewardship_create_form_uses_asset_ajax_select():
    host, _ = _create_tenants()
    client = Client()
    asset = client.post(
        "/api/v1/assets",
        data=json.dumps(
            {
                "qualified_name": "warehouse.patients.curated",
                "display_name": "Curated Patients",
                "asset_type": "dataset",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert asset.status_code == 201

    page = client.get(
        "/ui/operations/stewardship",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert page.status_code == 200
    assert b'data-ui-action-form="stewardship-create"' in page.content
    assert b"/api/v1/ui/model-select-options?source=assets" in page.content
    assert b"Create stewardship item" in page.content
    assert b"quality_exception" in page.content


@pytest.mark.django_db(transaction=True)
def test_access_request_create_form_uses_asset_ajax_select_and_prefills_requester():
    host, _ = _create_tenants()
    client = Client()
    asset = client.post(
        "/api/v1/assets",
        data=json.dumps(
            {
                "qualified_name": "governance.requests.orders",
                "display_name": "Orders Requests Asset",
                "asset_type": "dataset",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert asset.status_code == 201

    page = client.get(
        "/ui/operations/stewardship",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
        HTTP_X_USER_ID="reader@example.com",
    )
    assert page.status_code == 200
    assert b'data-ui-action-form="access-request-create"' in page.content
    assert b"/api/v1/ui/model-select-options?source=assets" in page.content
    assert b"Submit access request" in page.content
    assert b"reader@example.com" in page.content
    assert b"access_type" in page.content


@pytest.mark.django_db(transaction=True)
def test_orchestration_action_form_renders_for_admin():
    host, _ = _create_tenants()
    client = Client()
    project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "UI Action Project"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    ingestion = client.post(
        "/api/v1/ingestions",
        data=json.dumps(
            {"project_id": project.json()["id"], "connector": "dbt", "source": {"processed_entities": 1}}
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    workflow = client.post(
        "/api/v1/orchestration/workflows",
        data=json.dumps(
            {"name": "ui-orch-actions", "project_id": project.json()["id"], "steps": [{"step_id": "s1", "ingestion_id": ingestion.json()["id"]}]}
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    client.post(
        "/api/v1/orchestration/runs",
        data=json.dumps({"workflow_id": workflow.json()["id"]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    page = client.get(
        "/ui/operations/orchestration",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert page.status_code == 200
    assert b'data-ui-action-form="orchestration"' in page.content


@pytest.mark.django_db(transaction=True)
def test_orchestration_workflow_run_create_form_uses_ajax_selects():
    host, _ = _create_tenants()
    client = Client()
    definition = client.post(
        "/api/v1/workflows/definitions",
        data=json.dumps({"name": "Governance Review", "domain_ref": "governance"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert definition.status_code == 201
    asset = client.post(
        "/api/v1/assets",
        data=json.dumps(
            {
                "qualified_name": "governance.asset.patient",
                "display_name": "Patient Registry Asset",
                "asset_type": "dataset",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert asset.status_code == 201

    page = client.get(
        "/ui/operations/orchestration",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert page.status_code == 200
    assert b'data-ui-action-form="workflow-run-create"' in page.content
    assert b"/api/v1/ui/model-select-options?source=workflow_definitions" in page.content
    assert b"/api/v1/ui/model-select-options?source=assets" in page.content
    assert b"Queue workflow run" in page.content


@pytest.mark.django_db(transaction=True)
def test_agent_action_form_renders_with_input_fields():
    host, _ = _create_tenants()
    client = Client()
    client.post(
        "/api/v1/agent/runs",
        data=json.dumps({"prompt": "project:p monitor", "allowed_tools": ["quality.read"], "start_now": True}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    page = client.get(
        "/ui/operations/agent",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert page.status_code == 200
    assert b'data-ui-action-form="agent"' in page.content
    assert b"error message (for fail)" in page.content
    assert b"output JSON (for complete)" in page.content


@pytest.mark.django_db(transaction=True)
def test_printing_page_renders_jobs_and_gateways():
    host, _ = _create_tenants()
    client = Client()
    client.post(
        "/api/v1/printing/templates",
        data=json.dumps(
            {
                "name": "Shipping Label",
                "template_ref": "label/shipping-ui",
                "output_format": "pdf",
                "sample_payload": {"order_id": "42"},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    client.post(
        "/api/v1/printing/jobs",
        data=json.dumps(
            {
                "template_ref": "label/shipping-ui",
                "destination": "printer-a",
                "output_format": "pdf",
                "payload": {"order_id": "42"},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    client.post(
        "/api/v1/printing/gateways",
        data=json.dumps(
            {
                "gateway_ref": "gw-ui-test",
                "display_name": "Gateway UI Test",
                "status": "online",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    page = client.get(
        "/ui/operations/printing",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin,catalog.editor",
    )
    assert page.status_code == 200
    assert b"Shipping Label" in page.content
    assert b"Run test print" in page.content
    assert b"Define print template" in page.content
    assert b"Gateway UI Test" in page.content
    assert b'data-ui-action-form="print-job"' in page.content
    assert b'data-ui-action-form="print-gateway"' in page.content


@pytest.mark.django_db(transaction=True)
def test_user_portal_dashboard_renders_test_print_action():
    host, _ = _create_tenants()
    client = Client()
    client.post(
        "/api/v1/printing/templates",
        data=json.dumps(
            {
                "name": "Portal Label",
                "template_ref": "label/portal",
                "output_format": "pdf",
                "sample_payload": {"sample": True},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    client.post(
        "/api/v1/printing/gateways",
        data=json.dumps(
            {
                "gateway_ref": "printer-portal-1",
                "display_name": "Portal Printer",
                "status": "online",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    page = client.get(
        "/app",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
        HTTP_X_USER_ID="user-portal-1",
    )
    assert page.status_code == 200
    assert b"User Workspace" in page.content
    assert b"Test print" in page.content
    assert b'data-user-action="test-print"' in page.content
    assert b'data-user-action="create-template"' in page.content
    assert b'data-user-action="create-printer"' in page.content
    assert b'data-user-action="template-preview"' in page.content
    assert b'data-user-action="printer-status-update"' in page.content
    assert b"participant prefix" in page.content
    assert b"range start" in page.content
    assert b"range end" in page.content
    assert b"Serial position" in page.content
    assert b"label variants" in page.content
    assert b"PDF sheet preset" in page.content
    assert b"labels (optional, one per line)" in page.content
    assert b"Signed in as:" in page.content
    assert b"user-portal-1" in page.content
    assert b"catalog.editor" in page.content


@pytest.mark.django_db(transaction=True)
def test_user_portal_dashboard_includes_default_print_templates():
    host, _ = _create_tenants()
    client = Client()
    page = client.get(
        "/app",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert page.status_code == 200
    assert b"Zebra QR Label (9-pack ready)" in page.content
    assert b"A4 QR Sheet 65-up (38.1x21.2mm)" in page.content
