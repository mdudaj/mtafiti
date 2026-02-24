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


# Create your models here.
