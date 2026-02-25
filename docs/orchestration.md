# Workflow orchestration design notes

This note outlines a minimal orchestration layer that builds on the existing ingestion and connector model without introducing a large platform dependency too early.

## Goals

* Keep orchestration tenant-scoped and policy-aware.
* Reuse existing ingestion request/state contracts as the execution boundary.
* Support scheduled and event-driven runs with simple retry semantics.

## Execution model (initial)

Define a lightweight workflow as an ordered list of steps where each step triggers an ingestion/connector run and waits for terminal status.

Suggested workflow states:

* `queued`
* `running`
* `succeeded`
* `failed`
* `cancelled`

Each step should capture:

* `step_id`
* `connector`
* `input_ref` (payload pointer or inline params)
* `depends_on` (optional prior step ids)

## Triggering

Support two trigger types first:

1. **Schedule**: cron-style trigger per tenant.
2. **Event**: domain-event trigger (for example `ingestion.completed`).

Trigger evaluation should enqueue workflow runs; workers remain responsible for execution.

## Non-goals (initial)

* Cross-tenant workflow dependencies.
* Full DAG optimization and parallel fan-out planning.
* External workflow engine lock-in (Airflow/Argo) before interfaces stabilize.
