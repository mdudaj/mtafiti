# Notification delivery hardening

This increment hardens tenant-scoped notification delivery with provider abstraction, retry handling, and dead-lettering.

## Delivery model

`UserNotification` now tracks:

* `delivery_status`: `pending`, `sent`, `failed`, `dead_letter`
* retry controls: `attempts`, `max_attempts`, `next_attempt_at`
* outcomes: `delivered_at`, `dead_lettered_at`, `last_error`
* routing metadata: `provider`, `channel`

## APIs

* `GET|POST /api/v1/notifications`
  * create notifications (email/in-app/webhook)
  * list notifications with optional status/channel filters
* `POST /api/v1/notifications/dispatch`
  * process pending/failed queue items with bounded batch size
* `POST /api/v1/notifications/{notification_id}/retry`
  * reset and retry failed/dead-letter notifications

## Provider behavior

The current provider interface is pluggable through `provider` and `channel`.

* `email` and `in_app` simulate successful dispatch in scaffold mode.
* `webhook` requires `payload.webhook_url`; missing URL triggers retry/dead-letter flow.
