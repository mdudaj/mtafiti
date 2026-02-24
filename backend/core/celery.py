from __future__ import annotations

from celery import Task
from django_tenants.utils import schema_context


class TenantTask(Task):
    abstract = True

    def __call__(self, *args, **kwargs):
        schema_name = kwargs.get('tenant_schema')
        if not schema_name:
            raise ValueError('tenant_schema is required')
        with schema_context(schema_name):
            return super().__call__(*args, **kwargs)

