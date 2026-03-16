import pytest
from django.db import connection
from django.db.utils import DatabaseError
from django.test import Client


@pytest.mark.django_db(transaction=True)
def test_metrics_is_public_and_prometheus_formatted():
    client = Client()
    client.get('/healthz', HTTP_HOST='unknown.example')
    resp = client.get('/metrics', HTTP_HOST='unknown.example')
    assert resp.status_code == 200
    assert 'text/plain' in resp['Content-Type']
    body = resp.content.decode('utf-8')
    assert 'edmp_http_requests_total' in body
    assert 'edmp_http_request_latency_seconds' in body


@pytest.mark.django_db(transaction=True)
def test_readyz_db_error_updates_readiness_metric(monkeypatch):
    def raise_error():
        raise DatabaseError('db down')

    monkeypatch.setattr(connection, 'ensure_connection', raise_error)
    client = Client()
    failed = client.get('/readyz', HTTP_HOST='unknown.example')
    assert failed.status_code == 503

    metrics = client.get('/metrics', HTTP_HOST='unknown.example')
    assert metrics.status_code == 200
    assert 'edmp_db_readiness_errors_total' in metrics.content.decode('utf-8')
