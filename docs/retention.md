# Data retention & lifecycle design notes

This document captures a minimal design for tenant-scoped retention controls so EDMP can enforce predictable data and metadata lifecycles.

## Goals

* Keep retention rules tenant-scoped and auditable.
* Start with metadata-first enforcement (catalog + lineage + ingestion records), then expand to integrated data-plane systems.
* Keep policy decisions explicit and explainable (`what matched`, `why deleted/archived`, `who approved`).

## Retention model (initial)

Each rule should define:

* `scope`: asset type(s), tags, classifications, and optional owner filters
* `action`: `archive` or `delete`
* `retention_period`: ISO-8601 duration (example: `P365D`)
* `grace_period` (optional): additional delay before destructive actions
* `legal_hold` override: records under hold are excluded from deletion

Suggested defaults:

* `public` metadata: longer archive window, delayed delete
* `confidential`/`restricted`: shorter active lifetime with stricter review gates

## Execution lifecycle

1. **Evaluate** candidate assets by rule scope and age.
2. **Dry-run** result set with counts and sampled resources for review.
3. **Approve** destructive runs (tenant admin / policy admin).
4. **Execute** archive/delete as tenant-aware background tasks.
5. **Emit events + audit records** for every affected resource.

## API and eventing conventions

* API (future):
  * `POST /api/v1/retention/rules`
  * `GET /api/v1/retention/rules`
  * `POST /api/v1/retention/runs` (dry-run or execute)
* Events:
  * `retention.rule.created`
  * `retention.run.started`
  * `retention.asset.archived`
  * `retention.asset.deleted`
  * `retention.run.completed`

Each event should include `tenant_id`, `correlation_id`, `rule_id`, and run summary stats.
