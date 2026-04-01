# Operational runbooks and incident playbooks

This guide provides first-response procedures for common Mtafiti operational incidents.

For panel/alert definitions and severity thresholds, see [operations dashboards and alerts](operations-dashboards-alerts.md).

## Scope

Runbooks in this document cover:

* connector execution failures
* orchestration run failures
* queue backlog and worker lag
* OIDC/JWT rollout and key rotation operations

## Incident triage playbook (all incidents)

1. Confirm blast radius
   * Which tenant(s), endpoint(s), or workflow(s) are affected.
   * Whether writes are failing, reads are degraded, or both.
2. Check platform health
   * `GET /livez`, `GET /readyz`, and `GET /metrics`
   * Postgres/RabbitMQ pod health and restart state.
3. Capture evidence before mutation
   * correlation id(s), run ids, timestamps, and current status responses.
4. Stabilize
   * Stop new triggering actions (pause schedule/manual run creation if needed).
   * Prefer cancelling queued/running runs over deleting records.
5. Recover
   * Follow specific runbook below.
6. Verify and close
   * Re-run health checks, verify successful end-to-end run, and log remediation steps.

## Runbook: connector failures

### Connector detection signals

* `connector.run.failed` / `connector.run.cancelled` events.
* ingestion status transitions to `failed`.
* `/metrics` task failure counters increase.

### Connector verification commands

```bash
curl -sS http://localhost:8000/api/v1/connectors/runs?status=failed -H "Host: <tenant-host>"
curl -sS http://localhost:8000/api/v1/ingestions/<ingestion_id> -H "Host: <tenant-host>"
curl -sS http://localhost:8000/metrics | grep -E "edmp_celery_task_executions|edmp_celery_task_duration"
```

### Connector recovery steps

1. Identify failed `connector_run_id` and `ingestion_id`.
2. Confirm failure reason (`error_message`, classification/policy constraints, source payload issues).
3. Correct upstream payload/config issue.
4. Re-queue ingestion through normal API path; avoid direct DB edits.
5. Verify final run status is `succeeded`.

### Connector safety / rollback notes

* Do not delete failed runs during incident response; keep them for audit/evidence.
* If repeated failures occur, pause automation and require manual approval before retries.

## Runbook: orchestration failures

### Orchestration detection signals

* `orchestration.run.failed` events.
* orchestration monitor shows high failed run count.

### Orchestration verification commands

```bash
curl -sS http://localhost:8000/api/v1/orchestration/runs?status=failed -H "Host: <tenant-host>"
curl -sS http://localhost:8000/api/v1/orchestration/runs/<run_id>/transition -X POST \
  -H "Host: <tenant-host>" -H "Content-Type: application/json" -d '{"action":"cancel"}'
```

### Orchestration recovery steps

1. Inspect `step_results` and `error_message` to isolate failed step.
2. Validate referenced ingestion exists and belongs to expected project.
3. If run is still active and non-recoverable, cancel it.
4. Fix workflow definition / ingestion dependency.
5. Queue a fresh run and verify all steps complete successfully.

### Orchestration safety / rollback notes

* Prefer cancel + rerun over force-updating run status.
* Keep failed run history intact for post-incident analysis.

## Runbook: queue backlog and worker lag

### Queue backlog detection signals

* Rapid growth of `queued` connector/orchestration runs.
* Increased task duration and delayed completion.
* Worker pods healthy but throughput reduced.

### Queue backlog verification commands

```bash
curl -sS http://localhost:8000/api/v1/connectors/runs?status=queued -H "Host: <tenant-host>"
curl -sS http://localhost:8000/api/v1/orchestration/runs?status=queued -H "Host: <tenant-host>"
curl -sS http://localhost:8000/metrics | grep -E "edmp_celery_task_executions|edmp_celery_task_duration"
kubectl get pods -n edmp
kubectl logs deployment/mtafiti-platform-worker -n edmp --tail=200
```

### Queue backlog recovery steps

1. Confirm dependency health (Postgres, RabbitMQ, network).
2. Scale worker deployment if backlog is capacity-driven.
3. Temporarily reduce new run creation rate (manual gate).
4. Drain backlog and track queue depth trend to steady state.

### Queue backlog safety / rollback notes

* Scale gradually; avoid sudden spikes that overload DB or broker.
* If scaling worsens error rate, revert to prior replica count and investigate bottleneck.

## Post-incident checklist

* Document timeline, affected tenants, root cause, and mitigation.
* Capture follow-up actions in backlog (config hardening, alert tuning, retry policy).
* Add/adjust automated checks to detect recurrence earlier.

## Runbook: OIDC rollout and key rotation operations

### Prechecks

1. Confirm `EDMP_OIDC_JWT_SECRET` is configured in target environment.
2. Confirm issuer/audience values are explicitly set where required:
   * `EDMP_OIDC_ISSUER`
   * `EDMP_OIDC_AUDIENCE`
3. Confirm at least one test token per tenant with expected `sub`, `roles`, and `tid`.
4. Ensure fallback mode is currently enabled (`EDMP_OIDC_REQUIRED=false`) before strict rollout.

### Phased rollout sequence

1. **Stage 1 (observe)**: keep `EDMP_OIDC_REQUIRED=false`, send bearer tokens from clients/gateway, and monitor `401`/`403` patterns.
2. **Stage 2 (enforce in non-prod)**: set `EDMP_OIDC_REQUIRED=true` in lower environments and run smoke checks.
3. **Stage 3 (production canary)**: enable `EDMP_OIDC_REQUIRED=true` for canary environment/slice.
4. **Stage 4 (full enforcement)**: enable globally after canary success and stable error rates.

### Key rotation procedure (`EDMP_OIDC_JWT_SECRET`)

1. Generate new secret and store in secret manager (do not commit in repo).
2. Coordinate token issuer rotation so new tokens are minted with the new key.
3. Deploy app config with new `EDMP_OIDC_JWT_SECRET`.
4. Run smoke checks below.
5. If failures spike, rollback to prior secret and revalidate issuer side.

### Smoke checks (valid/invalid/tenant mismatch)

```bash
# valid token -> expect 200/201 on authorized endpoints
curl -sS http://localhost:8000/api/v1/assets \
  -H "Host: <tenant-host>" \
  -H "Authorization: Bearer <valid-token>"

# invalid signature token -> expect 401 with invalid_token_signature
curl -sS http://localhost:8000/api/v1/assets \
  -H "Host: <tenant-host>" \
  -H "Authorization: Bearer <bad-signature-token>"

# tenant claim mismatch token -> expect 403 with token_tenant_mismatch
curl -sS http://localhost:8000/api/v1/assets \
  -H "Host: <tenant-host>" \
  -H "Authorization: Bearer <wrong-tid-token>"
```

### Rollback / safety notes

* On authentication incident, first set `EDMP_OIDC_REQUIRED=false` to restore controlled header fallback in emergency mode.
* Keep prior key material available until new-key validation is complete across all clients.
* Do not rotate issuer and secret simultaneously unless a tested dual-step plan is in place.

## Runbook: repository branch protection

Use this runbook when repository administrators need to reapply or verify the `main` branch protection contract after CI changes, repository migration, or GitHub settings drift.

### Branch protection preconditions

1. Repository admin access to `mdudaj/mtafiti`.
2. GitHub authentication available through `GH_TOKEN`, `GITHUB_TOKEN`, or `gh auth login`.
3. Required CI jobs already present in `.github/workflows/ci.yml`.

### Apply the repository merge policy and branch protection rule

Run the repository helper from the workspace root:

```bash
python3 .github/scripts/configure_branch_protection.py
```

To inspect the payload before mutating GitHub settings, use:

```bash
python3 .github/scripts/configure_branch_protection.py --dry-run
```

### Repository merge policy contract

The helper also configures repository-level merge behavior so the delivery workflow matches project policy:

* squash merge enabled
* merge commits disabled
* rebase merges disabled
* auto-merge enabled for green PRs
* head branches deleted automatically after merge

### Branch protection required checks

The helper enforces these required status checks on `main`:

* `docs-gate`
* `src-tests (shard 0/4)`
* `src-tests (shard 1/4)`
* `src-tests (shard 2/4)`
* `src-tests (shard 3/4)`
* `performance-baseline-tests`

It also enforces administrator coverage and the required workflow checks while keeping the approval count at zero so green PRs can auto-merge without an additional review gate.

### Branch protection verification

1. Confirm the helper prints the `main` branch payload or update result without API errors.
2. Open GitHub repository settings and verify `main` requires the checks listed above.
3. Confirm the repository allows squash merge, enables auto-merge, deletes branches on merge, and disallows merge-commit/rebase merge paths.
4. Confirm the branch still requires the PR path and workflow checks, but does not require an additional approving review or conversation-resolution gate.

### Branch protection safety / rollback notes

* If CI job names change, update `.github/scripts/configure_branch_protection.py` first and rerun the helper.
* Prefer reapplying the helper over editing GitHub settings manually so repository policy stays auditable in Git.
