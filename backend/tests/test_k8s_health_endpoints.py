import pytest
from django.db import connection
from django.db.utils import DatabaseError
from django.test import Client


@pytest.mark.django_db(transaction=True)
def test_healthz_does_not_require_tenant_host():
    client = Client()
    resp = client.get('/healthz', HTTP_HOST='unknown.example', HTTP_X_CORRELATION_ID='corr-1')
    assert resp.status_code == 200
    assert resp.json() == {'status': 'ok'}
    assert resp.headers['X-Correlation-Id'] == 'corr-1'


@pytest.mark.django_db(transaction=True)
def test_livez_does_not_require_tenant_host():
    client = Client()
    resp = client.get('/livez', HTTP_HOST='unknown.example')
    assert resp.status_code == 200
    assert resp.json() == {'status': 'ok'}


@pytest.mark.django_db(transaction=True)
def test_readyz_does_not_require_tenant_host_and_checks_db():
    client = Client()
    resp = client.get('/readyz', HTTP_HOST='unknown.example')
    assert resp.status_code == 200
    assert resp.json() == {'status': 'ok'}


@pytest.mark.django_db(transaction=True)
def test_readyz_returns_503_when_db_unavailable(monkeypatch):
    def raise_error():
        raise DatabaseError('db down')

    monkeypatch.setattr(connection, 'ensure_connection', raise_error)

    client = Client()
    resp = client.get('/readyz', HTTP_HOST='unknown.example')
    assert resp.status_code == 503
    assert resp.json() == {'status': 'not-ready'}
