import json
import logging

from django.http import JsonResponse
from django.test import RequestFactory

from core.logging import (
    CorrelationIdFilter,
    JsonFormatter,
    correlation_id_var,
    get_correlation_id,
    get_request_id,
    get_tenant_id,
    get_user_id,
)
from core.middleware import CorrelationIdMiddleware, RequestContextMiddleware


def test_correlation_id_context_is_set_and_reset():
    factory = RequestFactory()
    seen: list[str | None] = []

    def view(request):
        seen.append(get_correlation_id())
        return JsonResponse({'ok': True})

    resp = CorrelationIdMiddleware(view)(factory.get('/healthz', HTTP_X_CORRELATION_ID='corr-123'))
    assert resp.status_code == 200
    assert resp.headers['X-Correlation-Id'] == 'corr-123'
    assert seen == ['corr-123']
    assert get_correlation_id() is None


def test_request_context_middleware_sets_and_resets_fields():
    factory = RequestFactory()
    seen: list[tuple[str | None, str | None, str | None]] = []
    request = factory.get('/healthz', HTTP_X_USER_ID='user-1', HTTP_X_REQUEST_ID='req-9')
    request.tenant = type('Tenant', (), {'schema_name': 't_test'})()

    def view(request):
        seen.append((get_tenant_id(), get_user_id(), get_request_id()))
        return JsonResponse({'ok': True})

    resp = RequestContextMiddleware(view)(request)
    assert resp.status_code == 200
    assert seen == [('t_test', 'user-1', 'req-9')]
    assert get_tenant_id() is None
    assert get_user_id() is None
    assert get_request_id() is None


def test_json_formatter_includes_correlation_id():
    filt = CorrelationIdFilter()
    formatter = JsonFormatter()

    record = logging.LogRecord(
        name='test',
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='hello',
        args=(),
        exc_info=None,
    )
    assert filt.filter(record) is True
    payload = json.loads(formatter.format(record))
    assert payload['message'] == 'hello'
    assert payload['correlation_id'] is None
    assert payload['tenant_id'] is None
    assert payload['user_id'] is None
    assert payload['request_id'] is None

    token = correlation_id_var.set('corr-9')
    try:
        record2 = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname=__file__,
            lineno=2,
            msg='hello2',
            args=(),
            exc_info=None,
        )
        assert filt.filter(record2) is True
        payload2 = json.loads(formatter.format(record2))
        assert payload2['message'] == 'hello2'
        assert payload2['correlation_id'] == 'corr-9'
    finally:
        correlation_id_var.reset(token)
