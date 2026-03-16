# Metrics design notes

This note defines a minimal metrics increment for Mtafiti operations.

## Goals

* Expose Prometheus-compatible metrics at a stable endpoint.
* Cover the first reliability signals for API and worker paths.
* Keep tenant data isolation intact by exporting platform metrics only (no per-tenant payload data).

## API/server metrics (initial)

Expose `GET /metrics` without tenant host requirements and include:

* HTTP request count by route/method/status.
* HTTP request latency histogram (p50/p95/p99 derivable).
* In-flight request gauge.
* 5xx error rate from response codes.

## Worker/dependency metrics (initial)

Include:

* Celery task execution count and failure count by task name.
* Celery task latency histogram (queue wait + run duration where available).
* DB connectivity error counter for readiness failures.

## SLO starter set

Define initial service objectives:

1. API availability: `>= 99.9%` monthly for successful non-5xx responses.
2. API latency: p95 `< 300ms` for catalog/list APIs under baseline load.
3. Worker reliability: `>= 99%` successful ingestion task completion (excluding invalid requests).

## Non-goals (initial)

* Per-tenant usage billing metrics.
* Custom business KPI dashboards.
* Full tracing-derived RED/USE correlation (can follow in a tracing increment).

## Baseline performance checks

See [performance baseline](performance-baseline.md) for repeatable API/worker load profiles and CI-enforced latency thresholds.
See [operations dashboards and alerts](operations-dashboards-alerts.md) for operator panel and threshold definitions.
