from __future__ import annotations

import time

from celery import Task
from django_tenants.utils import schema_context

from .logging import correlation_id_var, request_id_var, tenant_id_var, user_id_var
from .metrics import CELERY_TASK_DURATION_SECONDS, CELERY_TASK_EXECUTIONS


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
        start = time.perf_counter()
        task_name = self.name or self.__class__.__name__
        try:
            with schema_context(schema_name):
                result = super().__call__(*args, **task_kwargs)
            CELERY_TASK_EXECUTIONS.labels(task=task_name, status='success').inc()
            return result
        except Exception:
            CELERY_TASK_EXECUTIONS.labels(task=task_name, status='failure').inc()
            raise
        finally:
            CELERY_TASK_DURATION_SECONDS.labels(task=task_name).observe(time.perf_counter() - start)
            correlation_id_var.reset(corr_token)
            user_id_var.reset(user_token)
            request_id_var.reset(request_token)
            tenant_id_var.reset(tenant_token)
