from django.contrib import admin

from .models import Domain, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('id', 'schema_name', 'name', 'created_on')
    search_fields = ('schema_name', 'name')


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('id', 'domain', 'tenant', 'is_primary')
    search_fields = ('domain',)
