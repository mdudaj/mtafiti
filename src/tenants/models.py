import re
from urllib.parse import urlsplit

from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Tenant(TenantMixin):
    name = models.CharField(max_length=100, unique=True)
    created_on = models.DateField(auto_now_add=True)

    # Auto-create the schema when a tenant is saved.
    auto_create_schema = True

    def __str__(self) -> str:
        return self.name


def normalize_domain(value: str) -> str:
    value = (value or '').strip()
    if not value:
        return value

    if '://' in value:
        parsed = urlsplit(value)
        if parsed.hostname:
            return parsed.hostname.rstrip('.').lower()
        value = parsed.netloc or parsed.path

    value = value.split('/', 1)[0].split('?', 1)[0].split('#', 1)[0]
    value = value.rsplit('@', 1)[-1]
    value = value.rstrip('.')

    # Strip port (best-effort; IPv6 URLs should use the scheme form and be
    # handled via urlsplit above).
    if ':' in value and not value.startswith('['):
        value = value.split(':', 1)[0]

    return value.lower()


def normalize_subdomain_label(value: str) -> str:
    normalized = re.sub(r'[^a-z0-9-]+', '-', (value or '').strip().lower())
    normalized = re.sub(r'-+', '-', normalized).strip('-')
    return normalized


def build_service_tenant_domain(service: str, tenant_slug: str, base_domain: str) -> str:
    normalized_service = normalize_subdomain_label(service)
    normalized_tenant = normalize_subdomain_label(tenant_slug)
    normalized_base = normalize_domain(base_domain)
    if not normalized_service or not normalized_tenant or not normalized_base:
        raise ValueError('service, tenant_slug, and base_domain are required')
    return f'{normalized_service}.{normalized_tenant}.{normalized_base}'


def parse_service_tenant_domain(hostname: str, base_domain: str) -> tuple[str, str] | None:
    normalized_host = normalize_domain(hostname)
    normalized_base = normalize_domain(base_domain)
    if not normalized_host or not normalized_base:
        return None
    suffix = f'.{normalized_base}'
    if not normalized_host.endswith(suffix):
        return None
    labels = normalized_host[: -len(suffix)].split('.')
    if len(labels) != 2:
        return None
    service, tenant_slug = (
        normalize_subdomain_label(labels[0]),
        normalize_subdomain_label(labels[1]),
    )
    if not service or not tenant_slug:
        return None
    return service, tenant_slug


class Domain(DomainMixin):
    def _normalize(self) -> None:
        if self.domain:
            self.domain = normalize_domain(self.domain)

    def clean_fields(self, exclude=None) -> None:
        self._normalize()
        return super().clean_fields(exclude=exclude)

    def clean(self) -> None:
        super().clean()
        self._normalize()

    def save(self, *args, **kwargs):
        self._normalize()
        return super().save(*args, **kwargs)


class TenantServiceRoute(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name='service_routes'
    )
    service_key = models.CharField(max_length=64)
    tenant_slug = models.CharField(max_length=64)
    base_domain = models.CharField(max_length=253)
    domain = models.CharField(max_length=253, unique=True)
    workspace_path = models.CharField(max_length=128, blank=True, default='')
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['service_key', 'tenant_slug', 'base_domain'],
                name='uniq_tenant_service_route',
            ),
        ]

    def save(self, *args, **kwargs):
        self.service_key = normalize_subdomain_label(self.service_key)
        self.tenant_slug = normalize_subdomain_label(self.tenant_slug)
        self.base_domain = normalize_domain(self.base_domain)
        self.domain = build_service_tenant_domain(
            self.service_key, self.tenant_slug, self.base_domain
        )
        return super().save(*args, **kwargs)
