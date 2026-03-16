# Collaboration design notes

This note defines tenant-scoped collaborative document editing using ONLYOFFICE.

## Goals

* Provide secure, role-based collaborative editing per tenant.
* Preserve document history and auditability for governance workflows.
* Keep object storage tenancy boundaries explicit.

## Platform constraints

* Collaboration engine: **ONLYOFFICE**.
* Document binaries stored in tenant-scoped object storage paths (MinIO-compatible).
* Integration secured with signed JWT payloads between Mtafiti and ONLYOFFICE.

## Document lifecycle conventions

* Create: register metadata in tenant schema and store object in tenant bucket/prefix.
* Edit: issue short-lived ONLYOFFICE token with tenant/user/document context.
* Save callback: validate token, persist version metadata, emit audit/event.
* Access control: enforce role checks before issuing editor/viewer sessions.

## Required audit coverage

* Document created
* Edit session started/ended
* Version checkpoint persisted
* Permission/ownership changed

Each record should include tenant id, actor id, correlation id, and timestamp.

## Non-goals (this increment)

* Cross-tenant document sharing.
* Replacing ONLYOFFICE with a different editor engine.

## API and events (implemented scaffold slice)

Endpoints:

* `GET/POST /api/v1/collaboration/documents`
* `GET/PATCH /api/v1/collaboration/documents/<document_id>`
* `POST /api/v1/collaboration/documents/<document_id>/session` (`view|edit`)
* `GET/POST /api/v1/collaboration/documents/<document_id>/versions`

Events:

* `collaboration.document.created`
* `collaboration.session.started`
* `collaboration.session.viewed`
* `collaboration.version.persisted`
