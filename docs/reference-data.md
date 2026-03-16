# Reference data management (design notes)

These notes define a lightweight reference-data capability that fits the existing Mtafiti scaffold and keeps tenant isolation intact.

## Scope

Reference data in this context means small, shared lookup-style datasets used across domain assets and operational workflows (for example country codes, product hierarchies, status codes, and policy vocabularies).

Initial scope:

* Tenant-scoped reference dataset registration (name, owner, domain, version).
* Versioned value-set publishing with immutable snapshots.
* Controlled promotion flow (`draft` -> `approved` -> `active` -> `deprecated`).
* Linkage from catalog assets to the reference dataset/version they depend on.

## API and lifecycle conventions (implemented scaffold slice)

HTTP surface under `/api/v1/reference-data/...`:

* `POST /datasets` / `GET /datasets`
* `POST /datasets/<id>/versions`
* `POST /datasets/<id>/versions/<version>/activate`
* `GET /datasets/<id>/versions/<version>/values`

Current behavior:

* Dataset creation captures `name`, `owner`, and `domain` metadata.
* Version creation stores immutable value snapshots and supports `draft` or `approved` initial state.
* Activation enforces a single `active` version per dataset by deprecating any previously active version.
* Dataset listing returns an `active_version` convenience field.

Lifecycle expectations:

* Only one version should be `active` per dataset.
* Activation should emit an audit-style domain event including actor, tenant, dataset id, and version.
* Consumers should reference explicit versions for reproducible processing; `active` is a convenience alias for interactive use.

## Governance and interoperability

* Ownership and approvals align with governance workflows (`policy.admin` or delegated steward role).
* Validation hooks can reuse data quality rule execution for value-set constraints (uniqueness, allowed format, effective date windows).
* Data contracts can reference required dataset/version pairs to enforce producer-consumer compatibility.
