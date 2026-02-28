# Operational dashboards and alert rules

This document defines operator-facing dashboard panels and alert thresholds for EDMP runtime health.

## Dashboard specification

## 1) API reliability dashboard

Panels:

* **Request rate by route/method/status**
  * Metric: `edmp_http_requests_total`
  * Breakdown: `method`, `path`, `status`
* **API latency p50/p95/p99**
  * Metric: `edmp_http_request_latency_seconds`
  * Breakdown: `method`, `path`
* **5xx response rate**
  * Metric: `edmp_http_requests_total` filtered to `status=~"5.."`
* **In-flight requests**
  * Metric: `edmp_http_inflight_requests`

## 2) Worker outcomes dashboard

Panels:

* **Task success/failure count by task**
  * Metric: `edmp_celery_task_executions_total`
  * Breakdown: `task`, `status`
* **Task duration p50/p95**
  * Metric: `edmp_celery_task_duration_seconds`
  * Breakdown: `task`
* **Failure ratio per task**
  * Derived from success/failure counters.

## 3) Queue backlog and dependency dashboard

Panels:

* **Connector queued runs**
  * Source: `/api/v1/connectors/runs?status=queued`
* **Orchestration queued runs**
  * Source: `/api/v1/orchestration/runs?status=queued`
* **Readiness DB error counter**
  * Metric: `edmp_db_readiness_errors_total`

## Alert rules

## Severity levels

* **P1**: customer-visible outage or sustained write-path failure.
* **P2**: degraded service requiring urgent intervention.
* **P3**: warning trend requiring planned remediation.

## Rule set

1. **Readiness failures (P1/P2)**
   * Condition: `readyz` failure or `edmp_db_readiness_errors_total` increasing continuously.
   * Threshold:
     * P1: readiness failing for `>= 5 minutes`.
     * P2: readiness flaps for `>= 3 occurrences in 10 minutes`.
2. **Task failure spike (P2/P3)**
   * Condition: `edmp_celery_task_executions_total{status="failure"}` spike by task.
   * Threshold:
     * P2: failure ratio `>= 20%` for 10 minutes.
     * P3: failure ratio `>= 10%` for 15 minutes.
3. **Queue backlog growth (P2/P3)**
   * Condition: queued connector/orchestration runs increasing without drain.
   * Threshold:
     * P2: queued count strictly increasing for 15 minutes.
     * P3: queued count above normal baseline for 30 minutes.
4. **API latency degradation (P2/P3)**
   * Condition: p95 request latency above baseline.
   * Threshold:
     * P2: p95 `> 500ms` for 10 minutes on core list APIs.
     * P3: p95 `> 350ms` for 15 minutes.
5. **API 5xx rate increase (P1/P2)**
   * Condition: `5xx / total` exceeds baseline.
   * Threshold:
     * P1: `>= 5%` for 5 minutes.
     * P2: `>= 2%` for 10 minutes.

## Alert-to-runbook triage mapping

* **Readiness failures** -> `operations-runbooks.md`:
  * Incident triage playbook
  * Queue backlog and worker lag runbook (dependency health steps)
* **Task failure spike** -> `operations-runbooks.md`:
  * Connector failures runbook
  * Orchestration failures runbook
* **Queue backlog growth** -> `operations-runbooks.md`:
  * Queue backlog and worker lag runbook
* **Auth-related spikes (401/403)** -> `operations-runbooks.md`:
  * OIDC rollout and key rotation operations runbook

## Implementation notes

* Start with these thresholds as defaults, then calibrate from observed baseline.
* Keep alert payloads actionable: include tenant host, route/task labels, and top failing dimensions.
