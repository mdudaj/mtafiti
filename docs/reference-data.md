# Reference data management (design notes)

These notes define a lightweight reference-data capability that fits the existing EDMP scaffold and keeps tenant isolation intact.

## Scope

Reference data in this context means small, shared lookup-style datasets used across domain assets and operational workflows (for example country codes, product hierarchies, status codes, and policy vocabularies).

Initial scope:

* Tenant-scoped reference dataset registration (name, owner, domain, version).
* Versioned value-set publishing with immutable snapshots.
* Controlled promotion flow (`draft` -> `approved` -> `active` -> `deprecated`).
* Linkage from catalog assets to the reference dataset/version they depend on.

## API and lifecycle conventions

Suggested first HTTP surface under `/api/v1/reference-data/...`:

* `POST /datasets` / `GET /datasets`
* `POST /datasets/<id>/versions`
* `POST /datasets/<id>/versions/<version>/activate`
* `GET /datasets/<id>/versions/<version>/values`

Lifecycle expectations:

* Only one version should be `active` per dataset.
* Activation should emit an audit-style domain event including actor, tenant, dataset id, and version.
* Consumers should reference explicit versions for reproducible processing; `active` is a convenience alias for interactive use.

## Governance and interoperability

* Ownership and approvals align with governance workflows (`policy.admin` or delegated steward role).
* Validation hooks can reuse data quality rule execution for value-set constraints (uniqueness, allowed format, effective date windows).
* Data contracts can reference required dataset/version pairs to enforce producer-consumer compatibility.
