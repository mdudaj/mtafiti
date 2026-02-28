import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from core.models import ProjectInvitation, ProjectMembership, UserNotification
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
def test_project_create_and_sync_scoping_for_ingestion_and_orchestration():
    host, _ = _create_tenants()
    client = Client()
    project = client.post(
        "/api/v1/projects",
        data=json.dumps(
            {
                "name": "Cancer Study",
                "institution_ref": "institution-a",
                "sync_config": {"sources": ["fhir", "csv"]},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    assert project.json()["sync_config"]["sources"] == ["fhir", "csv"]

    ingestion = client.post(
        "/api/v1/ingestions",
        data=json.dumps(
            {
                "project_id": project_id,
                "connector": "dbt",
                "source": {"processed_entities": 3},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert ingestion.status_code == 201
    ingestion_id = ingestion.json()["id"]
    assert ingestion.json()["project_id"] == project_id

    listed_ingestions = client.get(f"/api/v1/ingestions?project_id={project_id}", HTTP_HOST=host)
    assert listed_ingestions.status_code == 200
    assert len(listed_ingestions.json()["items"]) == 1
    assert listed_ingestions.json()["items"][0]["id"] == ingestion_id

    workflow = client.post(
        "/api/v1/orchestration/workflows",
        data=json.dumps(
            {
                "name": "project-sync",
                "project_id": project_id,
                "steps": [{"step_id": "s1", "ingestion_id": ingestion_id}],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert workflow.status_code == 201
    assert workflow.json()["project_id"] == project_id

    orchestration_run = client.post(
        "/api/v1/orchestration/runs",
        data=json.dumps({"workflow_id": workflow.json()["id"]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert orchestration_run.status_code == 201
    assert orchestration_run.json()["project_id"] == project_id


@pytest.mark.django_db(transaction=True)
def test_project_scoping_is_tenant_local():
    host_a, host_b = _create_tenants()
    client = Client()
    project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "Tenant A Program"}),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    project_id = project.json()["id"]

    assert len(client.get("/api/v1/projects", HTTP_HOST=host_a).json()["items"]) == 1
    assert client.get("/api/v1/projects", HTTP_HOST=host_b).json()["items"] == []

    ingestion_other_tenant = client.post(
        "/api/v1/ingestions",
        data=json.dumps(
            {
                "project_id": project_id,
                "connector": "dbt",
                "source": {},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host_b,
    )
    assert ingestion_other_tenant.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_project_role_and_orchestration_project_validation(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()
    denied_project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "Program"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert denied_project.status_code == 403

    project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "Program"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    ingestion_no_project = client.post(
        "/api/v1/ingestions",
        data=json.dumps({"connector": "dbt", "source": {}}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert ingestion_no_project.status_code == 201

    mismatch_workflow = client.post(
        "/api/v1/orchestration/workflows",
        data=json.dumps(
            {
                "name": "wf-mismatch",
                "project_id": project_id,
                "steps": [
                    {
                        "step_id": "s1",
                        "ingestion_id": ingestion_no_project.json()["id"],
                    }
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert mismatch_workflow.status_code == 400
    assert mismatch_workflow.json()["error"] == "step_project_mismatch"


@pytest.mark.django_db(transaction=True)
def test_project_member_invite_existing_user_sends_notification():
    host, _ = _create_tenants()
    client = Client()
    project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "Cancer Study"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    existing_project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "Existing Program"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    ProjectMembership.objects.create(
        project_id=existing_project.json()["id"],
        user_email="existing@example.com",
        role=ProjectMembership.Role.RESEARCHER,
    )

    invite = client.post(
        f"/api/v1/projects/{project.json()['id']}/members/invite",
        data=json.dumps({"email": "existing@example.com", "role": "principal_investigator"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="owner@example.com",
    )
    assert invite.status_code == 201
    assert invite.json()["delivery"] == "existing_user_notification"
    assert invite.json()["membership"]["user_email"] == "existing@example.com"
    assert invite.json()["membership"]["role"] == "principal_investigator"
    assert ProjectInvitation.objects.filter(email="existing@example.com").count() == 0
    assert (
        UserNotification.objects.filter(
            user_email="existing@example.com",
            channel=UserNotification.Channel.IN_APP,
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_project_member_invite_new_user_generates_one_time_link_and_acceptance():
    host, _ = _create_tenants()
    client = Client()
    project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "Cancer Study"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    invite = client.post(
        f"/api/v1/projects/{project.json()['id']}/members/invite",
        data=json.dumps({"email": "new-user@example.com", "role": "data_manager"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="owner@example.com",
    )
    assert invite.status_code == 201
    assert invite.json()["delivery"] == "one_time_login_link"
    assert "invite-login?token=" in invite.json()["invite_link"]
    assert invite.json()["invitation"]["id"]

    accept = client.post(
        "/api/v1/projects/invitations/accept",
        data=json.dumps({"token": invite.json()["invite_link"].split("token=")[-1]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="new-user@example.com",
    )
    assert accept.status_code == 200
    assert accept.json()["membership"]["user_email"] == "new-user@example.com"
    assert accept.json()["membership"]["role"] == "data_manager"
    assert accept.json()["invitation"]["status"] == "accepted"
    assert (
        UserNotification.objects.filter(
            user_email="new-user@example.com",
            channel=UserNotification.Channel.EMAIL,
        ).count()
        == 1
    )
