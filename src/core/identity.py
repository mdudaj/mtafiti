import os
import base64
import hashlib
import hmac
import json
import time

from django.http import JsonResponse


def _roles_enforced() -> bool:
    return os.environ.get('EDMP_ENFORCE_ROLES', '').lower() in {'1', 'true', 'yes'}


def _request_roles(request) -> set[str]:
    if hasattr(request, 'auth_roles'):
        return set(getattr(request, 'auth_roles'))
    raw = request.headers.get('X-User-Roles', '')
    return {role.strip() for role in raw.split(',') if role.strip()}


def roles_enforced() -> bool:
    return _roles_enforced()


def request_roles(request) -> set[str]:
    return _request_roles(request)


def _oidc_required() -> bool:
    return os.environ.get('EDMP_OIDC_REQUIRED', '').lower() in {'1', 'true', 'yes'}


def _b64url_decode(data: str) -> bytes:
    padded = data + '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode('utf-8'))


def _decode_unverified(token: str) -> tuple[dict, dict, str]:
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError('invalid_token_format')
    header_raw, payload_raw, signature = parts
    try:
        header = json.loads(_b64url_decode(header_raw))
        payload = json.loads(_b64url_decode(payload_raw))
    except Exception as exc:
        raise ValueError('invalid_token_encoding') from exc
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise ValueError('invalid_token_payload')
    return header, payload, signature


def _verify_hs256(token: str, secret: str) -> dict:
    header, payload, signature = _decode_unverified(token)
    if header.get('alg') != 'HS256':
        raise ValueError('unsupported_token_algorithm')
    signing_input = '.'.join(token.split('.')[:2]).encode('utf-8')
    expected_sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
    ).rstrip(b'=').decode('utf-8')
    if not hmac.compare_digest(expected_sig, signature):
        raise ValueError('invalid_token_signature')
    return payload


def _validate_registered_claims(payload: dict) -> None:
    now = int(time.time())
    exp = payload.get('exp')
    if exp is not None:
        try:
            exp = int(exp)
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid_token_exp') from exc
        if now >= exp:
            raise ValueError('token_expired')

    nbf = payload.get('nbf')
    if nbf is not None:
        try:
            nbf = int(nbf)
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid_token_nbf') from exc
        if now < nbf:
            raise ValueError('token_not_yet_valid')

    configured_issuer = os.environ.get('EDMP_OIDC_ISSUER')
    if configured_issuer and payload.get('iss') != configured_issuer:
        raise ValueError('invalid_token_issuer')

    configured_audience = os.environ.get('EDMP_OIDC_AUDIENCE')
    if configured_audience:
        accepted_audiences = {item.strip() for item in configured_audience.split(',') if item.strip()}
        token_aud = payload.get('aud')
        token_audiences = (
            {token_aud}
            if isinstance(token_aud, str)
            else set(token_aud or []) if isinstance(token_aud, list) else set()
        )
        if not token_audiences.intersection(accepted_audiences):
            raise ValueError('invalid_token_audience')

    subject = payload.get('sub')
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError('invalid_token_subject')


def _extract_roles_from_claims(payload: dict) -> set[str]:
    roles = payload.get('roles')
    if isinstance(roles, list):
        return {str(role).strip() for role in roles if str(role).strip()}
    if isinstance(roles, str):
        return {role.strip() for role in roles.split(',') if role.strip()}
    return set()


def authenticate_request(request):
    auth_header = request.headers.get('Authorization', '')
    has_bearer = auth_header.lower().startswith('bearer ')
    if not has_bearer:
        if _oidc_required():
            return JsonResponse({'error': 'missing_bearer_token'}, status=401)
        return None

    token = auth_header[7:].strip()
    if not token:
        return JsonResponse({'error': 'invalid_authorization_header'}, status=401)

    secret = os.environ.get('EDMP_OIDC_JWT_SECRET')
    if not secret:
        return JsonResponse({'error': 'oidc_not_configured'}, status=401)

    try:
        payload = _verify_hs256(token, secret)
        _validate_registered_claims(payload)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=401)

    roles = _extract_roles_from_claims(payload)
    user_id = payload['sub'].strip()
    tenant_claim = payload.get('tid')
    tenant_schema = getattr(getattr(request, 'tenant', None), 'schema_name', None)
    if tenant_claim is not None and tenant_schema and str(tenant_claim) != str(tenant_schema):
        return JsonResponse({'error': 'token_tenant_mismatch'}, status=403)

    request.auth_claims = payload
    request.auth_roles = roles
    request.auth_user_id = user_id
    request.META['HTTP_X_USER_ID'] = user_id
    request.META['HTTP_X_USER_ROLES'] = ','.join(sorted(roles))
    return None


def require_role(request, role: str):
    """Require a role for the request when EDMP_ENFORCE_ROLES is enabled.

    Returns None when access is allowed, otherwise returns a 403 JsonResponse.
    """
    if not _roles_enforced():
        return None
    if role in _request_roles(request):
        return None
    return JsonResponse({'error': 'forbidden'}, status=403)


def require_any_role(request, roles: set[str]):
    """Require one of the provided roles when EDMP_ENFORCE_ROLES is enabled."""
    if not _roles_enforced():
        return None
    request_roles = _request_roles(request)
    if request_roles.intersection(roles):
        return None
    return JsonResponse({'error': 'forbidden'}, status=403)
