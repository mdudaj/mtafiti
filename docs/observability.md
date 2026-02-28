# Observability design notes

This scaffold prioritizes cloud-native operational behavior: predictable probes, structured logs, and a clear path to metrics/tracing.

## Probes

* `GET /livez`: process-level health (always OK if the process is running)
* `GET /readyz`: dependency-level health (DB round-trip; returns `503` when DB is unavailable)

These endpoints bypass tenant resolution.

## Logging

* JSON console logs are enabled in Django settings.
* Requests include `X-Correlation-Id` via middleware; ingress can inject it for end-to-end tracing across services.

## Metrics (future)

When needed, expose `/metrics` (Prometheus) with at least:

* request latency (p50/p95/p99)
* 5xx rate
* Celery queue depth and task latency
* DB connection pool saturation / error rate

Current baseline checks for latency/error regression are documented in [performance baseline](performance-baseline.md).
Operational first-response and recovery steps are documented in [operations runbooks](operations-runbooks.md).
Dashboard and alert specification is documented in [operations dashboards and alerts](operations-dashboards-alerts.md).

## Tracing (future)

Adopt OpenTelemetry once service boundaries and dependencies expand beyond the initial scaffold. Correlation ids should remain stable even when full tracing is enabled.
