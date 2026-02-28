import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


def _create_tenant_host() -> str:
    host = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f"Tenant A {uuid.uuid4().hex[:6]}",
        )
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()
    return host


def _assert_contract_keys(payload: dict, expected_keys: set[str]) -> None:
    assert expected_keys.issubset(set(payload.keys()))


@pytest.mark.django_db(transaction=True)
def test_api_version_header_and_asset_contract_keys_are_stable():
    host = _create_tenant_host()
    client = Client()
    resp = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'warehouse.sales.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert resp.status_code == 201
    assert resp.headers['X-API-Version'] == 'v1'
    _assert_contract_keys(
        resp.json(),
        {'id', 'qualified_name', 'display_name', 'asset_type', 'properties', 'created_at', 'updated_at'},
    )


@pytest.mark.django_db(transaction=True)
def test_unsupported_api_version_is_rejected():
    host = _create_tenant_host()
    client = Client()
    resp = client.get('/api/v1/assets', HTTP_HOST=host, HTTP_X_API_VERSION='v2')
    assert resp.status_code == 400
    assert resp.headers['X-API-Version'] == 'v1'
    assert resp.json()['error'] == 'unsupported_api_version'
    assert resp.json()['supported_versions'] == ['v1']


@pytest.mark.django_db(transaction=True)
def test_project_and_ingestion_contract_fields_are_stable():
    host = _create_tenant_host()
    client = Client()

    project_resp = client.post(
        '/api/v1/projects',
        data=json.dumps({'name': 'Cancer Study', 'sync_config': {'source': 'fhir'}}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert project_resp.status_code == 201
    _assert_contract_keys(
        project_resp.json(),
        {'id', 'name', 'code', 'institution_ref', 'status', 'sync_config', 'created_at', 'updated_at'},
    )

    ingestion_resp = client.post(
        '/api/v1/ingestions',
        data=json.dumps({'project_id': project_resp.json()['id'], 'connector': 'dbt', 'source': {}}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert ingestion_resp.status_code == 201
    _assert_contract_keys(
        ingestion_resp.json(),
        {'id', 'project_id', 'connector', 'source', 'mode', 'status', 'created_at', 'updated_at'},
    )


@pytest.mark.django_db(transaction=True)
def test_stewardship_orchestration_and_agent_contract_fields_are_stable():
    host = _create_tenant_host()
    client = Client()

    stewardship_resp = client.post(
        '/api/v1/stewardship/items',
        data=json.dumps({'item_type': 'quality_exception', 'subject_ref': 'asset:warehouse.sales.orders'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert stewardship_resp.status_code == 201
    _assert_contract_keys(
        stewardship_resp.json(),
        {'id', 'item_type', 'subject_ref', 'status', 'severity', 'resolution', 'created_at', 'updated_at'},
    )

    ingestion_resp = client.post(
        '/api/v1/ingestions',
        data=json.dumps({'connector': 'dbt', 'source': {}}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert ingestion_resp.status_code == 201

    workflow_resp = client.post(
        '/api/v1/orchestration/workflows',
        data=json.dumps(
            {
                'name': 'nightly-refresh',
                'steps': [{'step_id': 'extract', 'ingestion_id': ingestion_resp.json()['id']}],
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert workflow_resp.status_code == 201
    _assert_contract_keys(
        workflow_resp.json(),
        {'id', 'name', 'status', 'trigger_type', 'steps', 'created_at', 'updated_at'},
    )

    agent_resp = client.post(
        '/api/v1/agent/runs',
        data=json.dumps({'prompt': 'Summarize incidents', 'allowed_tools': ['catalog.search']}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert agent_resp.status_code == 201
    _assert_contract_keys(
        agent_resp.json(),
        {'id', 'status', 'prompt', 'allowed_tools', 'actor_id', 'created_at', 'updated_at'},
    )


@pytest.mark.django_db(transaction=True)
def test_user_and_notification_contract_fields_are_stable():
    host = _create_tenant_host()
    client = Client()
    user_resp = client.post(
        '/api/v1/users',
        data=json.dumps({'email': 'contract-user@example.com', 'display_name': 'Contract User'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert user_resp.status_code == 201
    assert user_resp.headers['X-API-Version'] == 'v1'
    _assert_contract_keys(
        user_resp.json(),
        {'id', 'email', 'display_name', 'status', 'last_login_at', 'created_at', 'updated_at'},
    )

    detail_resp = client.get(
        f"/api/v1/users/{user_resp.json()['id']}",
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert detail_resp.status_code == 200
    _assert_contract_keys(
        detail_resp.json(),
        {'id', 'email', 'display_name', 'status', 'last_login_at', 'created_at', 'updated_at'},
    )

    notification_resp = client.post(
        '/api/v1/notifications',
        data=json.dumps(
            {
                'user_email': 'contract-user@example.com',
                'notification_type': 'invite',
                'channel': 'in_app',
                'payload': {'message': 'hello'},
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert notification_resp.status_code == 201
    _assert_contract_keys(
        notification_resp.json(),
        {
            'id',
            'user_email',
            'notification_type',
            'channel',
            'provider',
            'delivery_status',
            'attempts',
            'max_attempts',
            'payload',
            'created_at',
        },
    )

    dispatch_resp = client.post(
        '/api/v1/notifications/dispatch',
        data=json.dumps({'limit': 5}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert dispatch_resp.status_code == 200
    _assert_contract_keys(dispatch_resp.json(), {'processed', 'sent', 'failed', 'dead_letter'})


@pytest.mark.django_db(transaction=True)
def test_membership_and_invitation_contract_fields_are_stable():
    host = _create_tenant_host()
    client = Client()

    project_resp = client.post(
        '/api/v1/projects',
        data=json.dumps({'name': 'Contract Membership'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()['id']

    create_existing_user = client.post(
        '/api/v1/users',
        data=json.dumps({'email': 'member-existing@example.com', 'display_name': 'Existing Member'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert create_existing_user.status_code == 201

    existing_invite = client.post(
        f'/api/v1/projects/{project_id}/members/invite',
        data=json.dumps({'email': 'member-existing@example.com', 'role': 'researcher'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
        HTTP_X_USER_ID='owner@example.com',
    )
    assert existing_invite.status_code == 201
    _assert_contract_keys(existing_invite.json()['membership'], {'id', 'project_id', 'user_email', 'role', 'status', 'created_at', 'updated_at'})

    lifecycle_resp = client.post(
        f"/api/v1/projects/{project_id}/members/{existing_invite.json()['membership']['id']}/lifecycle",
        data=json.dumps({'action': 'change_role', 'role': 'data_manager'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
        HTTP_X_USER_ID='owner@example.com',
    )
    assert lifecycle_resp.status_code == 200
    _assert_contract_keys(lifecycle_resp.json()['membership'], {'id', 'project_id', 'user_email', 'role', 'status', 'created_at', 'updated_at'})
    _assert_contract_keys(lifecycle_resp.json()['history'], {'id', 'membership_id', 'action', 'created_at'})

    new_invite = client.post(
        f'/api/v1/projects/{project_id}/members/invite',
        data=json.dumps({'email': 'member-new@example.com', 'role': 'data_manager'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
        HTTP_X_USER_ID='owner@example.com',
    )
    assert new_invite.status_code == 201
    _assert_contract_keys(
        new_invite.json()['invitation'],
        {
            'id',
            'project_id',
            'email',
            'role',
            'status',
            'token_attempts',
            'max_token_attempts',
            'expires_at',
            'created_at',
            'updated_at',
        },
    )

    resend_resp = client.post(
        f"/api/v1/projects/invitations/{new_invite.json()['invitation']['id']}/resend",
        data=json.dumps({}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
        HTTP_X_USER_ID='owner@example.com',
    )
    assert resend_resp.status_code == 200
    _assert_contract_keys(resend_resp.json()['invitation'], {'id', 'project_id', 'email', 'role', 'status', 'expires_at', 'created_at', 'updated_at'})

    revoke_resp = client.post(
        f"/api/v1/projects/invitations/{new_invite.json()['invitation']['id']}/revoke",
        data=json.dumps({}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
        HTTP_X_USER_ID='owner@example.com',
    )
    assert revoke_resp.status_code == 200
    _assert_contract_keys(revoke_resp.json()['invitation'], {'id', 'project_id', 'email', 'role', 'status', 'created_at', 'updated_at'})
