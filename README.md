# Enterprise Data Management Platform (EDMP)

This repository contains an initial scaffold for a Kubernetes-native, multi-tenant EDMP backend.

## Design docs

* [Architecture overview](docs/architecture.md)
* [Roadmap (design increments)](docs/roadmap.md)
* [Identity & access](docs/identity.md)
* [Identity lifecycle and membership operations](docs/identity-lifecycle.md)
* [Notification delivery hardening](docs/notification-delivery.md)
* [Governance & policy](docs/governance.md)
* [Governance workflows](docs/governance-workflows.md)
* [Workflow engine and UI](docs/workflow-ui.md)
* [API versioning policy](docs/api-versioning.md)
* [API change communication checklist](docs/api-change-management.md)
* [Data privacy management](docs/privacy.md)
* [Data residency controls](docs/residency.md)
* [Data access requests](docs/access-requests.md)
* [Platform security baseline](docs/platform-security.md)
* [Platform services baseline](docs/platform-services.md)
* [Catalog growth](docs/catalog.md)
* [Printing and gateway](docs/printing.md)
* [Collaboration](docs/collaboration.md)
* [Notebook infrastructure](docs/notebooks.md)
* [Policy enforcement](docs/policy.md)
* [Data retention & lifecycle](docs/retention.md)
* [Audit events](docs/audit.md)
* [Request context propagation](docs/request-context.md)
* [Ingestion](docs/ingestion.md)
* [Connector execution model](docs/connectors.md)
* [Workflow orchestration](docs/orchestration.md)
* [Project membership and invitations](docs/project-membership.md)
* [Invitation security hardening](docs/invitation-security.md)
* [Lineage](docs/lineage.md)
* [Search](docs/search.md)
* [Data quality](docs/data-quality.md)
* [Data contracts](docs/data-contracts.md)
* [Data products](docs/data-products.md)
* [Data sharing](docs/data-sharing.md)
* [Agentic AI execution](docs/agentic-ai.md)
* [Self-reflective implementation workflow](docs/self-reflective-implementation.md)
* [Metadata versioning](docs/metadata-versioning.md)
* [Reference data management](docs/reference-data.md)
* [Master data management](docs/master-data.md)
* [Data classification taxonomy](docs/classification.md)
* [Business glossary](docs/glossary.md)
* [Data stewardship operations](docs/stewardship.md)
* [Observability](docs/observability.md)
* [Metrics](docs/metrics.md)
* [Performance baseline](docs/performance-baseline.md)
* [Operational runbooks and incident playbooks](docs/operations-runbooks.md)
* [Operational dashboards and alert rules](docs/operations-dashboards-alerts.md)
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
* Python code contributions should follow PEP 8 conventions.

### Run tests

```bash
docker compose up -d --wait postgres

cd backend
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements-dev.txt

export POSTGRES_DB=edmp_test POSTGRES_USER=edmp POSTGRES_PASSWORD=edmp POSTGRES_HOST=localhost POSTGRES_PORT=5432
pytest

# faster local feedback (skip dedicated perf baseline lane)
pytest -q -k "not performance_baseline"

# run perf baseline separately
pytest -q tests/test_performance_baseline.py

# optional cleanup
docker compose down
```

Note: Django creates a separate test database (e.g. `test_edmp_test`) during `pytest`, so the configured `POSTGRES_USER` must have the `CREATEDB` privilege (or be a superuser).
