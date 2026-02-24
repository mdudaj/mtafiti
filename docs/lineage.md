# Lineage design notes

This scaffold’s catalog currently models only `DataAsset` records. Lineage is the next metadata-plane increment: a graph of relationships between assets (dataset → model, table → dashboard, etc.).

## Goals

* Keep lineage **tenant-scoped** (edges live in the tenant schema).
* Support **incremental upserts** (connectors update subsets of the graph).
* Provide a simple query surface for “upstream/downstream” traversal.

## Data model (proposed)

Minimum edge fields:

* `id` (UUID)
* `from_asset_id` (UUID; FK → `DataAsset`)
* `to_asset_id` (UUID; FK → `DataAsset`)
* `edge_type` (string; examples: `reads_from`, `writes_to`, `derived_from`)
* `properties` (JSON; optional connector-specific metadata)
* `created_at` / `updated_at`

Recommended constraints:

* Unique (`from_asset_id`, `to_asset_id`, `edge_type`) per tenant.

## API shape (proposed)

Tenant-scoped endpoints:

* `POST /api/v1/lineage/edges` → create/upsert a set of edges
* `GET /api/v1/lineage/edges?asset_id=<uuid>&direction=upstream|downstream&depth=<n>` → query edges

Notes:

* Query responses should include both `edges` and referenced `assets` (to avoid N+1 calls).
* Depth should be capped server-side (e.g. max 5) to avoid expensive traversals.

## Events (optional)

If event publishing is enabled, emit:

* `lineage.edge.upserted`

