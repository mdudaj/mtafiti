# Enterprise Data Management Platform (EDMP)

This repository contains an initial scaffold for a Kubernetes-native, multi-tenant EDMP backend.

## Design docs

* [Architecture overview](docs/architecture.md)
* [Kubernetes deployment notes](docs/kubernetes.md)

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
