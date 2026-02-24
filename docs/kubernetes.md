# Kubernetes deployment notes (scaffold)

This project’s backend is designed to run as a stateless service in Kubernetes. The manifests in `deploy/k8s/` are **examples** to help bootstrap the platform design.

## Health probes

The Deployment example uses:

* liveness: `GET /livez`
* readiness: `GET /readyz`

These endpoints do **not** require tenant host resolution.

## Example manifests

See:

* `deploy/k8s/backend.yaml`

Notes:

* Provide PostgreSQL connectivity via `POSTGRES_*` env vars.
* Provide broker connectivity via `CELERY_BROKER_URL` (RabbitMQ).
* `DJANGO_SECRET_KEY` should be provided via a Kubernetes Secret.

