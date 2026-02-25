# Data quality design notes

This document captures a minimal, tenant-safe approach for introducing data quality checks into EDMP without expanding runtime complexity too early.

## Goals

* Keep quality checks **declarative** (rules attached to assets and ingestion flows).
* Keep execution **async-first** (evaluate in workers, not request path).
* Keep results **tenant-scoped** with clear ownership and auditability.

## Rule model (initial)

Attach lightweight quality expectations to dataset-like assets:

* freshness threshold (for example: max age in minutes)
* null-rate thresholds for critical fields
* uniqueness expectation for selected keys

Suggested rule fields:

* `rule_id` (UUID)
* `asset_id`
* `rule_type`
* `params` (JSON object)
* `severity` (`warning` | `error`)

## Evaluation lifecycle

1. Ingestion (or scheduled trigger) queues a quality-evaluation task.
2. Worker evaluates rules and stores a compact result record.
3. Result status updates the latest quality state for the target asset.

Suggested statuses:

* `pass`
* `warn`
* `fail`
* `error` (evaluation/runtime issue)

## Events and metrics

When eventing is enabled, publish:

* `quality.check.completed`
* `quality.check.failed`

Metrics should include rule evaluation latency and pass/fail counters by tenant and rule type.
