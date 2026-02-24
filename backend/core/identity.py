import os

from django.http import JsonResponse


def _roles_enforced() -> bool:
    return os.environ.get('EDMP_ENFORCE_ROLES', '').lower() in {'1', 'true', 'yes'}


def _request_roles(request) -> set[str]:
    raw = request.headers.get('X-User-Roles', '')
    return {role.strip() for role in raw.split(',') if role.strip()}


def require_role(request, role: str):
    """Require a role for the request when EDMP_ENFORCE_ROLES is enabled.

    Returns None when access is allowed, otherwise returns a 403 JsonResponse.
    """
    if not _roles_enforced():
        return None
    if role in _request_roles(request):
        return None
    return JsonResponse({'error': 'forbidden'}, status=403)
