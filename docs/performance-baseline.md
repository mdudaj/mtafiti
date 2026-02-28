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
3. **API paginated catalog profile**
   * Run 40x `GET /api/v1/assets?page=1&page_size=20`.
   * Measures bounded-response latency and verifies pagination path performance.
4. **API notification queue profile**
   * Seed 200 notifications, then run 40x `GET /api/v1/notifications?status=pending&page=1&page_size=50`.
   * Measures filtered queue-list latency under moderate volume.
5. **Worker ping profile**
   * 30x `core.tasks.ping` task executions via `TenantTask`.
   * Measures task execution latency and verifies task metrics emission.

## Baseline thresholds (CI gate)

* Health endpoint p95 latency `< 100ms`.
* Asset list endpoint p95 latency `< 300ms`.
* Paginated asset list endpoint p95 latency `< 250ms`.
* Notification list endpoint p95 latency `< 300ms`.
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

## Query/index review notes

High-frequency list filters observed in current APIs:

* `ingestions`: `project_id`, `status`, recency sort
* `connector_runs`: `status`, `ingestion_id`, recency sort
* `orchestration_runs`: `project_id`, `workflow_id`, `status`, recency sort
* `projects`: `status`, recency sort
* `project_memberships`: `project_id`, `status`, recency sort
* `user_notifications`: `delivery_status`, `next_attempt_at`, `user_email`, recency sort

Current hardening in this wave includes bounded page sizes plus explicit DB indexes for the filter/sort combinations above.

Next optimization path for Wave 3:

1. Add pagination defaults and capped page sizes for high-volume list APIs.
2. Introduce selective field projection for list responses.
3. Add database index review for the most common filter combinations (`status`, `project_id`, `workflow_id`).
