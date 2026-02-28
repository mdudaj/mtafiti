# Ingestion design notes

This scaffold now includes a minimal ingestion request API (`POST /api/v1/ingestions`, `GET /api/v1/ingestions/<id>`) to capture intent and track status. It intentionally does **not** implement ingestion connectors yet, but it should be designed so that connector execution can be added without changing the core multi-tenant / catalog foundations.

## Goals

* Keep ingestion **connector-style** (many sources; consistent platform entrypoints).
* Keep ingestion **async-first** (accept → validate → enqueue → process).
* Preserve **tenant isolation** (all persistence happens inside the tenant schema).

## Ingestion entrypoints (HTTP-first)

Recommended first API shape (tenant-scoped):

* `POST /api/v1/ingestions` → create an ingestion request (returns an `ingestion_id`)
* `GET /api/v1/ingestions/<id>` → get status + counters

Initial payload (suggested):

* `connector`: string (`"dbt"`, `"snowflake"`, `"s3"`, etc.)
* `source`: connector-specific object (opaque to the platform initially)
* `mode`: `"snapshot"` | `"incremental"` (optional)
* `project_id`: optional tenant-local project scope for connector sync ownership

The handler should:

1. validate the request shape (basic schema + size limits)
2. persist an ingestion record (status = `queued`)
3. enqueue a Celery task with the `ingestion_id`

## Tenant project scoping (implemented)

Ingestion requests now support optional project-level scoping inside a tenant:

* `POST /api/v1/projects` and `GET /api/v1/projects`
* `POST /api/v1/ingestions` accepts optional `project_id`
* `GET /api/v1/ingestions?project_id=<project_id>` filters ingestion requests by project

## Background execution (Celery → later Jobs)

Phase 1 (small/medium ingestions):

* Celery task reads the ingestion record, performs normalization, writes `DataAsset` records.

Phase 2 (long-running / heavy ingestions):

* Keep the *same* HTTP surface.
* Execute ingestion as a Kubernetes Job and report progress back to the ingestion record.

## Events (optional)

If `RABBITMQ_URL` is configured, emit domain events:

* `ingestion.created`
* `ingestion.completed`
* `ingestion.failed`

Routing keys should follow the existing convention (see `docs/events.md`).
