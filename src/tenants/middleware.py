import os

from django.db import connection
from django.db.models import Q
from django.http import JsonResponse
from django_tenants.middleware.main import TenantMainMiddleware

from .models import TenantServiceRoute, normalize_domain, normalize_subdomain_label


class EDMPTenantMiddleware(TenantMainMiddleware):
    """
    Enforce tenant resolution before ORM access.

    Requests without a resolvable tenant are rejected rather than silently
    falling back to the public schema.
    """

    # Normalized paths (no trailing slashes). We normalize request paths via
    # rstrip('/') before matching.
    PUBLIC_ENDPOINT_PATHS = {'/healthz', '/livez', '/readyz', '/metrics'}
    PUBLIC_ENDPOINT_PREFIXES = ('/api/v1/tenants', '/admin')

    def _resolve_service_route(self, hostname: str):
        normalized_host = normalize_domain(hostname)
        route = (
            TenantServiceRoute.objects.select_related('tenant')
            .filter(domain=normalized_host, is_enabled=True)
            .first()
        )
        if route:
            return route

        base_domain = normalize_domain(
            os.environ.get('EDMP_BASE_DOMAIN', 'edmp.co.tz')
        )
        suffix = f'.{base_domain}'
        if not normalized_host.endswith(suffix):
            return None
        labels = [
            normalize_subdomain_label(item)
            for item in normalized_host[: -len(suffix)].split('.')
            if item
        ]
        if len(labels) == 1:
            tenant_slug = labels[0]
            return (
                TenantServiceRoute.objects.select_related('tenant')
                .filter(
                    tenant_slug=tenant_slug,
                    base_domain=base_domain,
                    is_enabled=True,
                )
                .first()
            )
        if len(labels) == 2:
            first, second = labels
            return (
                TenantServiceRoute.objects.select_related('tenant')
                .filter(base_domain=base_domain, is_enabled=True)
                .filter(
                    Q(service_key=first, tenant_slug=second)
                    | Q(service_key=second, tenant_slug=first)
                )
                .first()
            )
        return None

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
        route = self._resolve_service_route(hostname)
        if route:
            request.tenant = route.tenant
            request.tenant.domain_url = hostname
            connection.set_tenant(request.tenant)
            self.setup_url_routing(request)
            return None
        return JsonResponse({'error': 'tenant_not_found'}, status=404)
