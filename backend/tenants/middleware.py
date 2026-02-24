from django.http import HttpResponseNotFound
from django_tenants.middleware.main import TenantMainMiddleware


class EDMPTenantMiddleware(TenantMainMiddleware):
    """
    Enforce tenant resolution before ORM access.

    Requests without a resolvable tenant are rejected rather than silently
    falling back to the public schema.
    """

    def no_tenant_found(self, request, hostname):
        return HttpResponseNotFound('Tenant not found')

