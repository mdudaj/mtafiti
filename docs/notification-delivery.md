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

* `email` and `in_app` run through the same dispatch pipeline and succeed in scaffold mode.
* `webhook` performs HTTP POST delivery with JSON payload; it requires `payload.webhook_url` using `http://` or `https://`.
* Webhook timeout is configured by `EDMP_NOTIFICATION_WEBHOOK_TIMEOUT_SECONDS` (clamped safety range `1..30` seconds).
* When `EDMP_NOTIFICATION_WEBHOOK_SECRET` is set, webhook requests include `X-EDMP-Signature: sha256=<hmac>` computed from the JSON payload body.
* Provider or delivery failures map to explicit errors (`missing_webhook_url`, `invalid_webhook_url`, `webhook_http_<code>`, `webhook_delivery_failed`) and flow into retry/dead-letter policy.
