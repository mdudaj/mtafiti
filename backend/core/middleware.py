import uuid

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
