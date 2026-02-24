# Metadata search design notes

This note describes a minimal, tenant-safe search increment for EDMP metadata.

## Goals

* Tenant-scoped metadata search across catalog fields (`name`, `asset_type`, `description`, `owner`, `tags`, `classifications`).
* Predictable API shape that stays aligned with existing `/api/v1/...` conventions.
* Incremental implementation path: start simple, then add relevance tuning and scale features.

## API shape (proposed)

* `GET /api/v1/search/assets?q=<query>&limit=<n>&offset=<n>`
* Tenant-scoped via the existing host-based tenant middleware.
* Response shape mirrors existing list endpoints:
  * `{"count": <int>, "results": [...]}` with stable pagination fields.

### Query behavior (initial)

* Case-insensitive substring match for `name` and `description`.
* Exact/normalized match for `asset_type`, `owner`, `tags`, and `classifications`.
* Deterministic ordering (for example: updated timestamp desc, then id) to keep pagination stable.

## Isolation and governance

* Execute all search queries inside the active tenant schema (no cross-tenant index sharing).
* Apply the same role checks used by catalog read APIs (`catalog.reader` or stronger when enforcement is enabled).
* Emit audit events for search API access only if governance policy requires query-level auditing (optional, not default).

## Implementation path

1. Start with DB-backed filtering on `DataAsset` fields (no external search service).
2. Add lightweight ranking heuristics (field weighting) only after baseline correctness.
3. Introduce optional asynchronous indexing and external search backend if tenant scale requires it.

## Non-goals (this increment)

* Full-text linguistic analysis, semantic search, or vector retrieval.
* Cross-tenant/global search views.
* Query language DSL beyond a single `q` parameter.
