from django.db import connection
from django.http import HttpResponseNotFound
from django_tenants.middleware.main import TenantMainMiddleware


class EDMPTenantMiddleware(TenantMainMiddleware):
    """
    Enforce tenant resolution before ORM access.

    Requests without a resolvable tenant are rejected rather than silently
    falling back to the public schema.
    """

    # Normalized paths (no trailing slashes). We normalize request paths via
    # rstrip('/') before matching.
    PUBLIC_ENDPOINT_PATHS = {'/healthz', '/livez', '/readyz'}
    PUBLIC_ENDPOINT_PREFIXES = ('/api/v1/tenants', '/admin')

    def process_request(self, request):
        # Kubernetes liveness/readiness probes typically don't send a tenant
        # hostname. For a multi-tenant app, these endpoints must still work to
        # allow the platform to determine container health.
        path = request.path.rstrip('/')
        is_public_path = any(path == p or path.startswith(f'{p}/') for p in self.PUBLIC_ENDPOINT_PREFIXES)
        if path in self.PUBLIC_ENDPOINT_PATHS or is_public_path:
            connection.set_schema_to_public()
            request.tenant = None
            return None
        return super().process_request(request)

    def no_tenant_found(self, request, hostname):
        return HttpResponseNotFound('Tenant not found')
