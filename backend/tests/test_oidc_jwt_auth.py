import base64
import hashlib
import hmac
import json
import time
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


def _create_tenant_host_and_schema() -> tuple[str, str]:
    host = f'tenant-{uuid.uuid4().hex[:6]}.example'
    with schema_context('public'):
        tenant = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f"Tenant {uuid.uuid4().hex[:6]}",
        )
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()
    return host, tenant.schema_name


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('utf-8')


def _make_hs256_jwt(payload: dict, secret: str) -> str:
    header = {'alg': 'HS256', 'typ': 'JWT'}
    encoded_header = _b64url(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    encoded_payload = _b64url(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    signing_input = f'{encoded_header}.{encoded_payload}'.encode('utf-8')
    signature = _b64url(hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest())
    return f'{encoded_header}.{encoded_payload}.{signature}'


@pytest.mark.django_db(transaction=True)
def test_oidc_required_rejects_missing_bearer_token(monkeypatch):
    monkeypatch.setenv('EDMP_OIDC_REQUIRED', 'true')
    monkeypatch.setenv('EDMP_OIDC_JWT_SECRET', 'secret-a')
    host, _ = _create_tenant_host_and_schema()
    client = Client()

    response = client.get('/api/v1/assets', HTTP_HOST=host)
    assert response.status_code == 401
    assert response.json()['error'] == 'missing_bearer_token'


@pytest.mark.django_db(transaction=True)
def test_oidc_valid_token_maps_roles_and_user(monkeypatch):
    monkeypatch.setenv('EDMP_OIDC_REQUIRED', 'true')
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    monkeypatch.setenv('EDMP_OIDC_JWT_SECRET', 'secret-a')
    host, schema = _create_tenant_host_and_schema()
    client = Client()
    token = _make_hs256_jwt(
        {
            'sub': 'alice@example.com',
            'roles': ['catalog.editor'],
            'tid': schema,
            'exp': int(time.time()) + 600,
        },
        'secret-a',
    )

    response = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.table', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {token}',
    )
    assert response.status_code == 201


@pytest.mark.django_db(transaction=True)
def test_oidc_rejects_invalid_signature_and_claim_mismatch(monkeypatch):
    monkeypatch.setenv('EDMP_OIDC_REQUIRED', 'true')
    monkeypatch.setenv('EDMP_OIDC_JWT_SECRET', 'secret-a')
    monkeypatch.setenv('EDMP_OIDC_ISSUER', 'https://issuer.example')
    monkeypatch.setenv('EDMP_OIDC_AUDIENCE', 'edmp-api')
    host, _ = _create_tenant_host_and_schema()
    client = Client()

    bad_signature = _make_hs256_jwt({'sub': 'bob', 'roles': ['catalog.reader']}, 'wrong-secret')
    denied_signature = client.get(
        '/api/v1/assets',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {bad_signature}',
    )
    assert denied_signature.status_code == 401
    assert denied_signature.json()['error'] == 'invalid_token_signature'

    bad_claims = _make_hs256_jwt(
        {
            'sub': 'bob',
            'roles': ['catalog.reader'],
            'iss': 'https://other.example',
            'aud': 'other-api',
            'exp': int(time.time()) + 600,
        },
        'secret-a',
    )
    denied_claims = client.get(
        '/api/v1/assets',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {bad_claims}',
    )
    assert denied_claims.status_code == 401
    assert denied_claims.json()['error'] == 'invalid_token_issuer'


@pytest.mark.django_db(transaction=True)
def test_oidc_enforces_tenant_claim_and_header_fallback_when_not_required(monkeypatch):
    monkeypatch.setenv('EDMP_OIDC_REQUIRED', 'false')
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    monkeypatch.setenv('EDMP_OIDC_JWT_SECRET', 'secret-a')
    host, schema = _create_tenant_host_and_schema()
    client = Client()

    mismatch_token = _make_hs256_jwt(
        {
            'sub': 'bob',
            'roles': ['catalog.editor'],
            'tid': f'{schema}_other',
            'exp': int(time.time()) + 600,
        },
        'secret-a',
    )
    mismatch = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.table.mismatch', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {mismatch_token}',
    )
    assert mismatch.status_code == 403
    assert mismatch.json()['error'] == 'token_tenant_mismatch'

    fallback = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'db.table.fallback', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_USER_ROLES='catalog.editor',
        HTTP_X_USER_ID='header-user',
    )
    assert fallback.status_code == 201


@pytest.mark.django_db(transaction=True)
def test_oidc_required_and_role_enforced_for_users_notifications_and_members(monkeypatch):
    monkeypatch.setenv('EDMP_OIDC_REQUIRED', 'true')
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    monkeypatch.setenv('EDMP_OIDC_JWT_SECRET', 'secret-a')
    host, schema = _create_tenant_host_and_schema()
    client = Client()

    users_without_token = client.get('/api/v1/users', HTTP_HOST=host)
    assert users_without_token.status_code == 401
    assert users_without_token.json()['error'] == 'missing_bearer_token'

    reader_token = _make_hs256_jwt(
        {
            'sub': 'reader@example.com',
            'roles': ['catalog.reader'],
            'tid': schema,
            'exp': int(time.time()) + 600,
        },
        'secret-a',
    )
    users_with_reader = client.get(
        '/api/v1/users',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {reader_token}',
    )
    assert users_with_reader.status_code == 200

    dispatch_with_reader = client.post(
        '/api/v1/notifications/dispatch',
        data=json.dumps({'limit': 1}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {reader_token}',
    )
    assert dispatch_with_reader.status_code == 403
    assert dispatch_with_reader.json()['error'] == 'forbidden'

    editor_token = _make_hs256_jwt(
        {
            'sub': 'editor@example.com',
            'roles': ['catalog.editor'],
            'tid': schema,
            'exp': int(time.time()) + 600,
        },
        'secret-a',
    )
    project_resp = client.post(
        '/api/v1/projects',
        data=json.dumps({'name': 'OIDC Scoped Project'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {editor_token}',
    )
    assert project_resp.status_code == 201
    members_with_reader = client.get(
        f"/api/v1/projects/{project_resp.json()['id']}/members",
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {reader_token}',
    )
    assert members_with_reader.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_oidc_required_for_invitation_accept_and_role_gated_notification_retry(monkeypatch):
    monkeypatch.setenv('EDMP_OIDC_REQUIRED', 'true')
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    monkeypatch.setenv('EDMP_OIDC_JWT_SECRET', 'secret-a')
    host, schema = _create_tenant_host_and_schema()
    client = Client()

    editor_token = _make_hs256_jwt(
        {
            'sub': 'editor@example.com',
            'roles': ['catalog.editor'],
            'tid': schema,
            'exp': int(time.time()) + 600,
        },
        'secret-a',
    )
    reader_token = _make_hs256_jwt(
        {
            'sub': 'reader@example.com',
            'roles': ['catalog.reader'],
            'tid': schema,
            'exp': int(time.time()) + 600,
        },
        'secret-a',
    )
    member_token = _make_hs256_jwt(
        {
            'sub': 'member-new@example.com',
            'roles': ['catalog.reader'],
            'tid': schema,
            'exp': int(time.time()) + 600,
        },
        'secret-a',
    )

    project_resp = client.post(
        '/api/v1/projects',
        data=json.dumps({'name': 'OIDC Invite Retry Project'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {editor_token}',
    )
    assert project_resp.status_code == 201

    invite_resp = client.post(
        f"/api/v1/projects/{project_resp.json()['id']}/members/invite",
        data=json.dumps({'email': 'member-new@example.com', 'role': 'researcher'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {editor_token}',
    )
    assert invite_resp.status_code == 201
    invite_token = invite_resp.json()['invite_link'].split('token=')[-1]

    accept_without_token = client.post(
        '/api/v1/projects/invitations/accept',
        data=json.dumps({'token': invite_token}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert accept_without_token.status_code == 401
    assert accept_without_token.json()['error'] == 'missing_bearer_token'

    accept_with_token = client.post(
        '/api/v1/projects/invitations/accept',
        data=json.dumps({'token': invite_token}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {member_token}',
    )
    assert accept_with_token.status_code == 200

    created_notification = client.post(
        '/api/v1/notifications',
        data=json.dumps(
            {
                'user_email': 'member-new@example.com',
                'notification_type': 'ops_alert',
                'channel': 'webhook',
                'payload': {'webhook_url': 'ftp://invalid.example.com'},
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {editor_token}',
    )
    assert created_notification.status_code == 201

    dispatch_resp = client.post(
        '/api/v1/notifications/dispatch',
        data=json.dumps({'limit': 10}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {editor_token}',
    )
    assert dispatch_resp.status_code == 200

    failed_list = client.get(
        '/api/v1/notifications?status=failed',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {reader_token}',
    )
    assert failed_list.status_code == 200
    notification_id = failed_list.json()['items'][0]['id']

    retry_with_reader = client.post(
        f'/api/v1/notifications/{notification_id}/retry',
        data=json.dumps({}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {reader_token}',
    )
    assert retry_with_reader.status_code == 403
    assert retry_with_reader.json()['error'] == 'forbidden'

    retry_with_editor = client.post(
        f'/api/v1/notifications/{notification_id}/retry',
        data=json.dumps({}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {editor_token}',
    )
    assert retry_with_editor.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_oidc_auth_responses_include_api_version_header_for_new_endpoints(monkeypatch):
    monkeypatch.setenv('EDMP_OIDC_REQUIRED', 'true')
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    monkeypatch.setenv('EDMP_OIDC_JWT_SECRET', 'secret-a')
    host, schema = _create_tenant_host_and_schema()
    client = Client()

    missing_token_users = client.get('/api/v1/users', HTTP_HOST=host)
    assert missing_token_users.status_code == 401
    assert missing_token_users.json()['error'] == 'missing_bearer_token'
    assert missing_token_users.headers['X-API-Version'] == 'v1'

    reader_token = _make_hs256_jwt(
        {
            'sub': 'reader@example.com',
            'roles': ['catalog.reader'],
            'tid': schema,
            'exp': int(time.time()) + 600,
        },
        'secret-a',
    )
    forbidden_dispatch = client.post(
        '/api/v1/notifications/dispatch',
        data=json.dumps({'limit': 1}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {reader_token}',
    )
    assert forbidden_dispatch.status_code == 403
    assert forbidden_dispatch.json()['error'] == 'forbidden'
    assert forbidden_dispatch.headers['X-API-Version'] == 'v1'

    accept_missing_token = client.post(
        '/api/v1/projects/invitations/accept',
        data=json.dumps({'token': 'placeholder'}),
        content_type='application/json',
        HTTP_HOST=host,
    )
    assert accept_missing_token.status_code == 401
    assert accept_missing_token.json()['error'] == 'missing_bearer_token'
    assert accept_missing_token.headers['X-API-Version'] == 'v1'

    editor_token = _make_hs256_jwt(
        {
            'sub': 'editor@example.com',
            'roles': ['catalog.editor'],
            'tid': schema,
            'exp': int(time.time()) + 600,
        },
        'secret-a',
    )
    retry_missing = client.post(
        '/api/v1/notifications/00000000-0000-0000-0000-000000000000/retry',
        data=json.dumps({}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {editor_token}',
    )
    assert retry_missing.status_code == 404
    assert retry_missing.json()['error'] == 'notification_not_found'
    assert retry_missing.headers['X-API-Version'] == 'v1'


@pytest.mark.django_db(transaction=True)
def test_oidc_tenant_claim_mismatch_on_users_and_invitation_accept(monkeypatch):
    monkeypatch.setenv('EDMP_OIDC_REQUIRED', 'true')
    monkeypatch.setenv('EDMP_ENFORCE_ROLES', 'true')
    monkeypatch.setenv('EDMP_OIDC_JWT_SECRET', 'secret-a')
    host, schema = _create_tenant_host_and_schema()
    client = Client()
    mismatch_token = _make_hs256_jwt(
        {
            'sub': 'mismatch@example.com',
            'roles': ['catalog.editor'],
            'tid': f'{schema}_other',
            'exp': int(time.time()) + 600,
        },
        'secret-a',
    )

    users_resp = client.get(
        '/api/v1/users',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {mismatch_token}',
    )
    assert users_resp.status_code == 403
    assert users_resp.json()['error'] == 'token_tenant_mismatch'
    assert users_resp.headers['X-API-Version'] == 'v1'

    accept_resp = client.post(
        '/api/v1/projects/invitations/accept',
        data=json.dumps({'token': 'placeholder'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_AUTHORIZATION=f'Bearer {mismatch_token}',
    )
    assert accept_resp.status_code == 403
    assert accept_resp.json()['error'] == 'token_tenant_mismatch'
    assert accept_resp.headers['X-API-Version'] == 'v1'
