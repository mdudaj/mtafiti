import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from core import notifications as notifications_module
from core.models import UserNotification
from tenants.models import Domain, Tenant


def _create_tenant_host() -> tuple[str, str]:
    host = f"tenant-{uuid.uuid4().hex[:6]}.example"
    with schema_context("public"):
        tenant = Tenant(
            schema_name=f"t_{uuid.uuid4().hex[:8]}",
            name=f"Tenant {uuid.uuid4().hex[:6]}",
        )
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()
    return host, tenant.schema_name


@pytest.mark.django_db(transaction=True)
def test_notification_dispatch_failure_and_dead_letter():
    host, _ = _create_tenant_host()
    client = Client()
    created = client.post(
        "/api/v1/notifications",
        data=json.dumps(
            {
                "user_email": "ops@example.com",
                "notification_type": "ops_alert",
                "channel": "webhook",
                "max_attempts": 1,
                "payload": {},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    dispatch = client.post(
        "/api/v1/notifications/dispatch",
        data=json.dumps({"limit": 10}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert dispatch.status_code == 200
    assert dispatch.json()["dead_letter"] == 1
    status = client.get("/api/v1/notifications?status=dead_letter", HTTP_HOST=host)
    assert status.status_code == 200
    assert status.json()["total"] == 1


@pytest.mark.django_db(transaction=True)
def test_notification_retry_from_dead_letter_succeeds():
    host, schema_name = _create_tenant_host()
    client = Client()
    with schema_context(schema_name):
        notification = UserNotification.objects.create(
            user_email="member@example.com",
            notification_type="invite",
            channel=UserNotification.Channel.EMAIL,
            delivery_status=UserNotification.DeliveryStatus.DEAD_LETTER,
            attempts=3,
            max_attempts=3,
            payload={"subject": "Invite"},
        )
    retried = client.post(
        f"/api/v1/notifications/{notification.id}/retry",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert retried.status_code == 200
    assert retried.json()["delivery_status"] == "sent"
    assert retried.json()["attempts"] == 1


@pytest.mark.django_db(transaction=True)
def test_webhook_notification_dispatch_success(monkeypatch):
    host, _ = _create_tenant_host()
    client = Client()
    monkeypatch.setattr(notifications_module, "_post_json", lambda *args, **kwargs: (True, ""))
    created = client.post(
        "/api/v1/notifications",
        data=json.dumps(
            {
                "user_email": "ops@example.com",
                "notification_type": "ops_alert",
                "channel": "webhook",
                "max_attempts": 2,
                "payload": {"webhook_url": "https://hooks.example.com/notify"},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    dispatch = client.post(
        "/api/v1/notifications/dispatch",
        data=json.dumps({"limit": 10}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert dispatch.status_code == 200
    assert dispatch.json()["sent"] == 1
    status = client.get("/api/v1/notifications?status=sent", HTTP_HOST=host)
    assert status.status_code == 200
    assert status.json()["total"] == 1


@pytest.mark.django_db(transaction=True)
def test_webhook_notification_invalid_url_fails():
    host, _ = _create_tenant_host()
    client = Client()
    created = client.post(
        "/api/v1/notifications",
        data=json.dumps(
            {
                "user_email": "ops@example.com",
                "notification_type": "ops_alert",
                "channel": "webhook",
                "max_attempts": 2,
                "payload": {"webhook_url": "ftp://invalid.example.com"},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert created.status_code == 201
    dispatch = client.post(
        "/api/v1/notifications/dispatch",
        data=json.dumps({"limit": 10}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert dispatch.status_code == 200
    assert dispatch.json()["failed"] == 1
    failed = client.get("/api/v1/notifications?status=failed", HTTP_HOST=host)
    assert failed.status_code == 200
    assert failed.json()["total"] == 1


@pytest.mark.django_db(transaction=True)
def test_webhook_notification_adds_signature_header_when_secret_configured(monkeypatch):
    host, _ = _create_tenant_host()
    client = Client()
    captured: dict[str, str] = {}

    class _FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(req, timeout):
        for key, value in req.header_items():
            captured[key.lower()] = value
        return _FakeResponse()

    monkeypatch.setenv("EDMP_NOTIFICATION_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setattr(notifications_module.urllib_request, "urlopen", _fake_urlopen)

    created = client.post(
        "/api/v1/notifications",
        data=json.dumps(
            {
                "user_email": "ops@example.com",
                "notification_type": "ops_alert",
                "channel": "webhook",
                "max_attempts": 2,
                "payload": {"webhook_url": "https://hooks.example.com/notify"},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert created.status_code == 201

    dispatch = client.post(
        "/api/v1/notifications/dispatch",
        data=json.dumps({"limit": 10}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    assert dispatch.status_code == 200
    assert dispatch.json()["sent"] == 1
    assert captured["x-edmp-signature"].startswith("sha256=")
