# Performance and scale baseline

This baseline defines repeatable performance checks for API and worker paths in the EDMP scaffold.

## Load profiles

The baseline uses deterministic local/CI profiles in `backend/tests/test_performance_baseline.py`:

1. **API health profile**
   * 40x `GET /healthz` requests.
   * Measures latency and error rate.
2. **API catalog profile**
   * Seed 20 assets, then run 40x `GET /api/v1/assets`.
   * Measures list latency and 5xx rate.
3. **Worker ping profile**
   * 30x `core.tasks.ping` task executions via `TenantTask`.
   * Measures task execution latency and verifies task metrics emission.

## Baseline thresholds (CI gate)

* Health endpoint p95 latency `< 100ms`.
* Asset list endpoint p95 latency `< 300ms`.
* Worker ping task p95 latency `< 200ms`.
* Error budget for the profiles: `0` responses with status `>=500`.

These thresholds are enforced by tests and are intended as guardrails against regressions, not production SLO replacements.

## How to run

```bash
docker compose up -d --wait postgres
cd backend
POSTGRES_DB=edmp_test POSTGRES_USER=edmp POSTGRES_PASSWORD=edmp POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
  ../.venv/bin/pytest -q tests/test_performance_baseline.py
```

## Bottleneck hypothesis and next optimization path

Primary near-term bottleneck risk is ORM-heavy list endpoints under larger datasets (N+1/serialization overhead) rather than middleware/probe paths.

Next optimization path for Wave 3:

1. Add pagination defaults and capped page sizes for high-volume list APIs.
2. Introduce selective field projection for list responses.
3. Add database index review for the most common filter combinations (`status`, `project_id`, `workflow_id`).
