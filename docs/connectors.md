# Connector execution model design notes

This note defines the next ingestion increment: executing connector runs in a way that keeps the ingestion API stable while supporting both short and long-running workloads.

## Goals

* Keep connector execution pluggable (`connector` + opaque `source` payload).
* Preserve tenant isolation for runtime state and persisted metadata.
* Support retries, progress reporting, and cancellation without changing request contracts.

## Execution model

Use two execution paths behind the same ingestion request API:

1. **Worker path (default)**: Celery executes small/medium ingestion runs directly.
2. **Job path (heavy)**: large or long-running runs are delegated to Kubernetes Jobs.

Selection should be policy/config-driven (payload size, connector type, expected duration), not client-driven.

## Runtime contract

Each run should transition through stable states:

`queued` → `running` → `succeeded` | `failed` | `cancelled`

The ingestion status endpoint remains the source of truth and should expose:

* current state
* start/finish timestamps
* retry count
* progress counters when available (processed/failed entities)

## Failure & retry rules (initial)

* Use bounded retries with exponential backoff for transient connector/dependency failures.
* Mark validation/authorization failures as terminal (no retry).
* Emit consistent completion/failure events for downstream observability and audit paths.

## Non-goals (initial)

* Connector SDK standardization across all external systems.
* Full workflow orchestration DAG semantics.
