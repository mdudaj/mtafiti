# Printing and gateway design notes

This note defines tenant-safe label printing using a gateway-based architecture.

## Goals

* Keep Kubernetes workloads isolated from direct printer network access.
* Provide reliable, auditable print execution for enterprise labeling.
* Support both Zebra (ZPL) and PDF/CUPS-style destinations through a controlled gateway.

## Architecture contract

* EDMP cluster never connects directly to site printers.
* Print jobs are requested in EDMP, then consumed and dispatched by a print gateway.
* RabbitMQ is the system transport for print lifecycle events.

## Print lifecycle

1. User submits print request.
2. System validates template, tenant scope, and authorization.
3. Print job is persisted with `pending` status.
4. Event is published (for example: `<tenant_id>.print.requested`).
5. Gateway pulls/subscribes and dispatches to local printer.
6. Gateway reports status (`completed`, `failed`, `retrying`).
7. EDMP finalizes audit record and job status.

## Gateway responsibilities

* Maintain secure outbound channel from site network to EDMP.
* Retry transient failures with bounded retry policy.
* Maintain offline queue while upstream is unavailable.
* Attach printer/driver metadata in completion/failure reports.

## Required metadata per print event

* `tenant_id`
* `correlation_id`
* `user_id` (if user-initiated)
* `timestamp`
* `job_id`

## Non-goals (this increment)

* Direct in-cluster printer management.
* Site-specific printer fleet provisioning automation.
