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
