import uuid

from django.http import JsonResponse

from .identity import authenticate_request
from .logging import correlation_id_var, request_id_var, tenant_id_var, user_id_var


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        correlation_id = request.headers.get('X-Correlation-Id') or str(uuid.uuid4())
        request.correlation_id = correlation_id
        token = correlation_id_var.set(correlation_id)
        try:
            response = self.get_response(request)
            response['X-Correlation-Id'] = correlation_id
            return response
        finally:
            correlation_id_var.reset(token)


class ApiVersionMiddleware:
    SUPPORTED_VERSION = 'v1'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/'):
            requested_version = request.headers.get('X-API-Version')
            if requested_version and requested_version != self.SUPPORTED_VERSION:
                response = JsonResponse(
                    {
                        'error': 'unsupported_api_version',
                        'supported_versions': [self.SUPPORTED_VERSION],
                    },
                    status=400,
                )
            else:
                response = self.get_response(request)
            response['X-API-Version'] = self.SUPPORTED_VERSION
            return response
        return self.get_response(request)


class OIDCJWTMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/'):
            auth_failure = authenticate_request(request)
            if auth_failure:
                return auth_failure
        return self.get_response(request)


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get('X-Request-Id') or request.headers.get('X-Request-ID')
        user_id = request.headers.get('X-User-Id')
        tenant_id = getattr(getattr(request, 'tenant', None), 'schema_name', None)
        request_id_token = request_id_var.set(request_id)
        user_id_token = user_id_var.set(user_id)
        tenant_id_token = tenant_id_var.set(tenant_id)
        try:
            return self.get_response(request)
        finally:
            request_id_var.reset(request_id_token)
            user_id_var.reset(user_id_token)
            tenant_id_var.reset(tenant_id_token)
