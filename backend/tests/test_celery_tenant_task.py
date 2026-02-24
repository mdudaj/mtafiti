import pytest

from core.tasks import ping


def test_celery_task_requires_tenant_schema():
    res = ping.apply(kwargs={})
    with pytest.raises(ValueError, match='tenant_schema is required'):
        res.get(propagate=True)


def test_celery_task_runs_with_tenant_schema():
    res = ping.apply(kwargs={'tenant_schema': 'public'})
    assert res.get() == 'pong:public'
