from __future__ import annotations

import json
import os
import hmac
import hashlib
from datetime import timedelta
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.db.models import Q
from django.utils import timezone

from .models import UserNotification


def _webhook_timeout_seconds() -> float:
    raw = os.environ.get("EDMP_NOTIFICATION_WEBHOOK_TIMEOUT_SECONDS", "5")
    try:
        parsed = float(raw)
    except ValueError:
        parsed = 5.0
    return min(max(parsed, 1.0), 30.0)


def _webhook_secret() -> str:
    return (os.environ.get("EDMP_NOTIFICATION_WEBHOOK_SECRET") or "").strip()


def _post_json(url: str, payload: dict, *, timeout: float, headers: dict[str, str] | None = None) -> tuple[bool, str]:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    req = urllib_request.Request(
        url,
        data=body,
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if status >= 400:
                return False, f"webhook_http_{status}"
    except urllib_error.HTTPError as exc:
        return False, f"webhook_http_{exc.code}"
    except (urllib_error.URLError, TimeoutError, OSError):
        return False, "webhook_delivery_failed"
    return True, ""


def _deliver_via_provider(notification: UserNotification) -> tuple[bool, str]:
    payload = notification.payload or {}
    if notification.channel in {
        UserNotification.Channel.EMAIL,
        UserNotification.Channel.IN_APP,
    }:
        return True, ""
    if notification.channel == UserNotification.Channel.WEBHOOK:
        if not isinstance(payload, dict):
            return False, "invalid_webhook_payload"
        webhook_url = payload.get("webhook_url")
        if not isinstance(webhook_url, str) or not webhook_url.strip():
            return False, "missing_webhook_url"
        if not webhook_url.startswith(("http://", "https://")):
            return False, "invalid_webhook_url"
        event_payload = {
            "user_email": notification.user_email,
            "notification_type": notification.notification_type,
            "channel": notification.channel,
            "provider": notification.provider,
            "payload": payload,
        }
        webhook_headers: dict[str, str] = {}
        secret = _webhook_secret()
        if secret:
            body = json.dumps(event_payload).encode("utf-8")
            signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            webhook_headers["X-EDMP-Signature"] = f"sha256={signature}"
        return _post_json(
            webhook_url,
            event_payload,
            timeout=_webhook_timeout_seconds(),
            headers=webhook_headers,
        )
    return False, "unsupported_notification_channel"


def dispatch_notification(notification: UserNotification) -> UserNotification:
    success, error = _deliver_via_provider(notification)
    notification.attempts += 1
    if success:
        notification.delivery_status = UserNotification.DeliveryStatus.SENT
        notification.delivered_at = timezone.now()
        notification.next_attempt_at = None
        notification.last_error = ""
        notification.save(
            update_fields=[
                "attempts",
                "delivery_status",
                "delivered_at",
                "next_attempt_at",
                "last_error",
            ]
        )
        return notification

    notification.last_error = error
    if notification.attempts >= notification.max_attempts:
        notification.delivery_status = UserNotification.DeliveryStatus.DEAD_LETTER
        notification.dead_lettered_at = timezone.now()
        notification.next_attempt_at = None
    else:
        notification.delivery_status = UserNotification.DeliveryStatus.FAILED
        notification.next_attempt_at = timezone.now() + timedelta(minutes=5)
    notification.save(
        update_fields=[
            "attempts",
            "delivery_status",
            "dead_lettered_at",
            "next_attempt_at",
            "last_error",
        ]
    )
    return notification


def process_notification_queue(*, limit: int = 100) -> dict[str, int]:
    now = timezone.now()
    qs = UserNotification.objects.filter(
        delivery_status__in=[
            UserNotification.DeliveryStatus.PENDING,
            UserNotification.DeliveryStatus.FAILED,
        ]
    ).filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
    notifications = list(qs.order_by("created_at")[:limit])
    summary = {"processed": 0, "sent": 0, "failed": 0, "dead_letter": 0}
    for notification in notifications:
        if notification.attempts >= notification.max_attempts:
            if notification.delivery_status != UserNotification.DeliveryStatus.DEAD_LETTER:
                notification.delivery_status = UserNotification.DeliveryStatus.DEAD_LETTER
                notification.dead_lettered_at = now
                notification.save(update_fields=["delivery_status", "dead_lettered_at"])
                summary["dead_letter"] += 1
            continue
        before = notification.delivery_status
        updated = dispatch_notification(notification)
        summary["processed"] += 1
        if updated.delivery_status == UserNotification.DeliveryStatus.SENT:
            summary["sent"] += 1
        elif updated.delivery_status == UserNotification.DeliveryStatus.DEAD_LETTER:
            summary["dead_letter"] += 1
        elif updated.delivery_status != before:
            summary["failed"] += 1
    return summary
