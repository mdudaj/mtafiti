from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Tenant(TenantMixin):
    name = models.CharField(max_length=100, unique=True)
    created_on = models.DateField(auto_now_add=True)

    # Auto-create the schema when a tenant is saved.
    auto_create_schema = True

    def __str__(self) -> str:
        return self.name


class Domain(DomainMixin):
    pass


# Create your models here.
