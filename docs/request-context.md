# Request context propagation (design notes)

This note defines a small, cross-cutting increment for carrying request context consistently across API handlers, events, logs, and asynchronous task execution.

## Why this increment

The scaffold already captures pieces of context (`X-Correlation-Id`, `X-User-Id`, tenant schema), but handling is currently endpoint/task specific.

A single context convention keeps upcoming increments (audit, policy, connector execution) consistent.

## Context envelope

Recommended minimal context fields:

* `correlation_id`: request/workflow correlation id
* `tenant_id`: tenant schema or tenant id
* `user_id`: authenticated/declared actor id
* `request_id`: optional edge/gateway request id

## Capture and propagation conventions

1. **API entry**: capture context from headers + tenant middleware state at request start.
2. **In-process use**: expose a request-local context accessor for views/services.
3. **Event publishing**: include the same context fields in every event envelope.
4. **Task enqueue**: attach context into task payload/headers when dispatching async work.
5. **Task execution**: restore context before business logic runs so logs/events are correlated.

## Logging conventions

Structured logs should include context fields when present:

* `correlation_id`
* `tenant_id`
* `user_id`

This enables queryable traces across API and worker logs without introducing distributed tracing infrastructure yet.

## Non-goals (for now)

* Full OpenTelemetry rollout.
* End-to-end trace/span propagation across external systems.
* Hard dependency on a specific API gateway header format.
