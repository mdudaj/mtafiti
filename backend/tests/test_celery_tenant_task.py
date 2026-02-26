import pytest

from core.logging import get_correlation_id, get_request_id, get_tenant_id, get_user_id
from core.tasks import context_ping, ping


def test_celery_task_requires_tenant_schema():
    res = ping.apply(kwargs={})
    with pytest.raises(ValueError, match='tenant_schema is required'):
        res.get(propagate=True)


def test_celery_task_runs_with_tenant_schema():
    res = ping.apply(kwargs={'tenant_schema': 'public'})
    assert res.get() == 'pong:public'


def test_celery_task_restores_context_from_kwargs():
    res = context_ping.apply(
        kwargs={
            'tenant_schema': 'public',
            'correlation_id': 'corr-1',
            'user_id': 'user-1',
            'request_id': 'req-1',
        }
    )
    assert res.get() == {
        'tenant_id': 'public',
        'correlation_id': 'corr-1',
        'user_id': 'user-1',
        'request_id': 'req-1',
    }
    assert get_tenant_id() is None
    assert get_correlation_id() is None
    assert get_user_id() is None
    assert get_request_id() is None
