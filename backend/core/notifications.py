from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .models import UserNotification


def _deliver_via_provider(notification: UserNotification) -> tuple[bool, str]:
    payload = notification.payload or {}
    if notification.channel == UserNotification.Channel.WEBHOOK:
        if not isinstance(payload, dict) or not payload.get("webhook_url"):
            return False, "missing_webhook_url"
    return True, ""


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
