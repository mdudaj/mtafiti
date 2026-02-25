# Catalog growth (design notes)

These notes capture the next catalog increment so implementation can extend the current `DataAsset` model without breaking tenant isolation or existing API behavior.

## Scope

Catalog growth in this scaffold focuses on metadata depth, not a full search or governance engine.

Initial scope:

* Keep tenant-scoped assets identified by UUID.
* Expand optional metadata fields (`description`, `owner`, `tags`, `classifications`) with stable API semantics.
* Preserve backwards compatibility for existing clients that only read `id`, `name`, and `asset_type`.
* Prepare for future linkage to lineage, glossary, and data product domains.

## API conventions

Current API surface remains:

* `GET /api/v1/assets`
* `POST /api/v1/assets`
* `GET /api/v1/assets/<id>`
* `PUT /api/v1/assets/<id>`

Conventions:

* `asset_type` should be treated as immutable after creation.
* Optional metadata fields should accept partial updates without forcing full object replacement.
* Tag/classification values should be stored as normalized string arrays for predictable filtering/indexing later.

## Interoperability

* Lineage edges should continue to reference asset UUIDs only, so metadata expansion does not affect lineage storage.
* Governance workflows can treat `owner` and `classifications` as policy inputs once policy enforcement is expanded.
* Data product and glossary features should attach to catalog assets through references, not by duplicating metadata fields.
