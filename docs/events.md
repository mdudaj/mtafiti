# EDMP events (design scaffold)

This repository includes a small, optional domain-event publisher (`backend/core/events.py`) to support an **async-first** platform design.

If `RABBITMQ_URL` is not configured, event publishing is a **no-op** (so local/dev and tests can run without a broker).

## Exchange and routing keys

* Exchange (topic): `EDMP_EVENT_EXCHANGE` (defaults to `edmp.events`)
* Routing key convention (recommended): `<tenant_schema>.<domain>.<event>`

Examples:

* `t_ab12cd34.control.tenant.created`
* `t_ab12cd34.catalog.asset.created`
* `t_ab12cd34.catalog.asset.updated`

## Event envelope (payload)

Events are published as JSON with the following envelope:

```json
{
  "event_type": "asset.updated",
  "tenant_id": "t_ab12cd34",
  "correlation_id": "c2d4f3b3-3c1d-4b62-bbc5-e2a0e0f5d2d3",
  "user_id": "alice@example.com",
  "timestamp": "2026-02-24T16:30:55.109Z",
  "data": {}
}
```

Field notes:

* `correlation_id`: taken from request context when available (or generated server-side).
* `user_id`: optional; currently taken from `X-User-Id` (scaffold) for audit/event metadata.
* `data`: event-specific payload (tenant, asset, policy, etc.).

## Schema validation gates

Event payloads are validated before publish. Validation covers:

* envelope fields (`event_type`, `tenant_id`, `correlation_id`, `timestamp`, `data`)
* domain family data contracts for:
  * `workflow.definition.*` and `workflow.run.*`
  * `orchestration.workflow.*` and `orchestration.run.*`
  * `stewardship.item.*`
  * `agent.run.*`
* audit payload shape for all `audit.*` events (`action`, `resource_type`, `resource_id`, `details`).

Regression tests in `backend/tests/test_event_payload.py` and `backend/tests/test_event_schema_gates.py` act as CI gates for schema conformance.

## Configuration

Required for publishing:

* `RABBITMQ_URL` (example: `amqp://user:pass@rabbitmq:5672/`)

Optional:

* `EDMP_EVENT_EXCHANGE` (default `edmp.events`)
