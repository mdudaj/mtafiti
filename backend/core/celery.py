from __future__ import annotations

from celery import Task
from django_tenants.utils import schema_context

from .logging import correlation_id_var, request_id_var, tenant_id_var, user_id_var


class TenantTask(Task):
    abstract = True

    def __call__(self, *args, **kwargs):
        task_kwargs = dict(kwargs)
        schema_name = task_kwargs.get('tenant_schema')
        if not schema_name:
            raise ValueError('tenant_schema is required')
        correlation_id = task_kwargs.pop('correlation_id', None)
        user_id = task_kwargs.pop('user_id', None)
        request_id = task_kwargs.pop('request_id', None)
        corr_token = correlation_id_var.set(correlation_id)
        user_token = user_id_var.set(user_id)
        request_token = request_id_var.set(request_id)
        tenant_token = tenant_id_var.set(schema_name)
        try:
            with schema_context(schema_name):
                return super().__call__(*args, **task_kwargs)
        finally:
            correlation_id_var.reset(corr_token)
            user_id_var.reset(user_token)
            request_id_var.reset(request_token)
            tenant_id_var.reset(tenant_token)
