# EDMP roadmap (design increments)

This repository is an intentionally small scaffold. This roadmap lists the next design increments that expand EDMP capabilities while keeping the runtime and operational surface area minimal.

## Near-term (next)

1. **Identity (authn) + roles (authz)**: define the OIDC/JWT integration points and a tenant-scoped role model.
2. **Audit events**: emit consistent audit events for mutating actions (tenants, assets, policies).
3. **Catalog growth**: add optional asset fields (owner, tags/classification) without breaking the minimal API.
4. **Lineage graph**: define an asset-to-asset relationship model (edges) and API conventions for querying/upserting it (see `docs/lineage.md`).
5. **Ingestion framework**: connector-style ingestion interfaces (HTTP, queued tasks, and job-style execution for long runs) (see `docs/ingestion.md`).
6. **Observability**: document SLOs and add a `/metrics` endpoint (Prometheus) when needed.

## Mid-term

* **Policy enforcement**: RBAC/ABAC checks in the API and background tasks, integrated with identity.
* **Search**: metadata search (indexing strategy + query API) while keeping tenant isolation intact.

## Out of scope for this scaffold (yet)

* Full workflow orchestration and scheduling (Airflow/Argo/etc.) — prefer clean integration points first.
* Large-scale data lake/warehouse provisioning — EDMP should integrate with existing compute/storage layers.
