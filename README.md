# Enterprise Data Management Platform (EDMP)

This repository contains an initial scaffold for a Kubernetes-native, multi-tenant EDMP backend.

## Design docs

* [Architecture overview](docs/architecture.md)
* [Roadmap (design increments)](docs/roadmap.md)
* [Identity & access](docs/identity.md)
* [Governance & policy](docs/governance.md)
* [Governance workflows](docs/governance-workflows.md)
* [Policy enforcement](docs/policy.md)
* [Data retention & lifecycle](docs/retention.md)
* [Audit events](docs/audit.md)
* [Ingestion](docs/ingestion.md)
* [Connector execution model](docs/connectors.md)
* [Workflow orchestration](docs/orchestration.md)
* [Lineage](docs/lineage.md)
* [Search](docs/search.md)
* [Data quality](docs/data-quality.md)
* [Data contracts](docs/data-contracts.md)
* [Reference data management](docs/reference-data.md)
* [Business glossary](docs/glossary.md)
* [Observability](docs/observability.md)
* [Metrics](docs/metrics.md)
* [Kubernetes deployment notes](docs/kubernetes.md)
* [OpenAPI (HTTP surface)](docs/openapi.yaml)
* [Eventing conventions](docs/events.md)

## Backend (Django + schema-per-tenant)

* Framework: Django
* Multi-tenancy: `django-tenants` (schema-per-tenant)
* Async: Celery (RabbitMQ-backed)
* Kubernetes probes:
  * `GET /healthz` / `GET /livez` (liveness; no tenant host required)
  * `GET /readyz` (readiness; performs a DB round-trip; no tenant host required)

### Local dev prerequisites

* Python 3.12+
* PostgreSQL (local service is fine)

### Run tests

```bash
cd backend
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements-dev.txt

export POSTGRES_DB=edmp_test POSTGRES_USER=edmp POSTGRES_PASSWORD=edmp POSTGRES_HOST=localhost POSTGRES_PORT=5432
pytest
```

Note: Django creates a separate test database (e.g. `test_edmp_test`) during `pytest`, so the configured `POSTGRES_USER` must have the `CREATEDB` privilege (or be a superuser).
