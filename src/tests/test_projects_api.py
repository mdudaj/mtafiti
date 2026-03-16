import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from core.models import (
    ProjectInvitation,
    ProjectMembership,
    ProjectMembershipRoleHistory,
    ProjectWorkspace,
    UserNotification,
    UserProfile,
)
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
    UserProfile.objects.create(email="existing@example.com", status=UserProfile.Status.ACTIVE)

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
    raw_token = invite.json()["invite_link"].split("token=")[-1]
    invitation_id = invite.json()["invitation"]["id"]
    stored_invitation = ProjectInvitation.objects.get(id=invitation_id)
    assert stored_invitation.token != raw_token
    assert len(stored_invitation.token) == 64

    accept = client.post(
        "/api/v1/projects/invitations/accept",
        data=json.dumps({"token": raw_token}),
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


@pytest.mark.django_db(transaction=True)
def test_project_invitation_revoke_and_resend_rotation():
    host, _ = _create_tenants()
    client = Client()
    project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "Security Study"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    invite = client.post(
        f"/api/v1/projects/{project.json()['id']}/members/invite",
        data=json.dumps({"email": "rotated@example.com", "role": "researcher"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="owner@example.com",
    )
    invitation_id = invite.json()["invitation"]["id"]
    first_token = invite.json()["invite_link"].split("token=")[-1]

    revoked = client.post(
        f"/api/v1/projects/invitations/{invitation_id}/revoke",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert revoked.status_code == 200
    assert revoked.json()["invitation"]["status"] == "revoked"
    denied_accept = client.post(
        "/api/v1/projects/invitations/accept",
        data=json.dumps({"token": first_token}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert denied_accept.status_code == 400
    assert denied_accept.json()["error"] == "invitation_revoked"

    resent = client.post(
        f"/api/v1/projects/invitations/{invitation_id}/resend",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert resent.status_code == 200
    second_token = resent.json()["invite_link"].split("token=")[-1]
    assert second_token != first_token
    assert resent.json()["invitation"]["status"] == "pending"

    old_token_rejected = client.post(
        "/api/v1/projects/invitations/accept",
        data=json.dumps({"token": first_token}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert old_token_rejected.status_code == 404

    accepted = client.post(
        "/api/v1/projects/invitations/accept",
        data=json.dumps({"token": second_token}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="rotated@example.com",
    )
    assert accepted.status_code == 200
    assert accepted.json()["invitation"]["status"] == "accepted"


@pytest.mark.django_db(transaction=True)
def test_user_directory_and_membership_lifecycle_endpoints():
    host, _ = _create_tenants()
    client = Client()
    created_user = client.post(
        "/api/v1/users",
        data=json.dumps({"email": "member@example.com", "display_name": "Member One"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert created_user.status_code == 201
    user_id = created_user.json()["id"]
    assert client.get(f"/api/v1/users/{user_id}", HTTP_HOST=host).status_code == 200

    updated_user = client.patch(
        f"/api/v1/users/{user_id}",
        data=json.dumps({"status": "disabled"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert updated_user.status_code == 200
    assert updated_user.json()["status"] == "disabled"

    project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "Lifecycle Study"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    invite = client.post(
        f"/api/v1/projects/{project.json()['id']}/members/invite",
        data=json.dumps({"email": "member@example.com", "role": "researcher"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="owner@example.com",
    )
    membership_id = invite.json()["membership"]["id"]
    members = client.get(f"/api/v1/projects/{project.json()['id']}/members", HTTP_HOST=host)
    assert members.status_code == 200
    assert len(members.json()["items"]) == 1

    changed_role = client.post(
        f"/api/v1/projects/{project.json()['id']}/members/{membership_id}/lifecycle",
        data=json.dumps({"action": "change_role", "role": "data_manager"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="owner@example.com",
    )
    assert changed_role.status_code == 200
    assert changed_role.json()["membership"]["role"] == "data_manager"

    revoked = client.post(
        f"/api/v1/projects/{project.json()['id']}/members/{membership_id}/lifecycle",
        data=json.dumps({"action": "revoke"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="owner@example.com",
    )
    assert revoked.status_code == 200
    assert revoked.json()["membership"]["status"] == "inactive"

    reactivated = client.post(
        f"/api/v1/projects/{project.json()['id']}/members/{membership_id}/lifecycle",
        data=json.dumps({"action": "reactivate"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ID="owner@example.com",
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["membership"]["status"] == "active"
    assert (
        ProjectMembershipRoleHistory.objects.filter(
            membership_id=membership_id,
            action__in=["change_role", "revoke", "reactivate"],
        ).count()
        == 3
    )


@pytest.mark.django_db(transaction=True)
def test_project_workspace_get_and_update():
    host, _ = _create_tenants()
    client = Client()
    project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "Workspace Study"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    workspace = client.get(f"/api/v1/projects/{project_id}/workspace", HTTP_HOST=host)
    assert workspace.status_code == 200
    assert workspace.json()["collaboration_enabled"] is True
    assert workspace.json()["data_management_enabled"] is True
    assert workspace.json()["document_management_enabled"] is True
    assert workspace.json()["collaboration_tools"] == []
    assert workspace.json()["data_resources"] == []
    assert workspace.json()["documents"] == []

    updated = client.patch(
        f"/api/v1/projects/{project_id}/workspace",
        data=json.dumps(
            {
                "collaboration_enabled": False,
                "data_management_enabled": True,
                "document_management_enabled": True,
                "collaboration_tools": ["shared-editor", "chat"],
                "data_resources": [{"kind": "dataset", "name": "raw-intake"}],
                "documents": [{"type": "protocol", "title": "Study Protocol v1"}],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert updated.status_code == 200
    assert updated.json()["collaboration_enabled"] is False
    assert updated.json()["collaboration_tools"] == ["shared-editor", "chat"]
    assert updated.json()["documents"][0]["type"] == "protocol"
    stored = ProjectWorkspace.objects.get(project_id=project_id)
    assert stored.collaboration_enabled is False
