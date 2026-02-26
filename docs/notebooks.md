# Notebook infrastructure design notes

This note defines tenant-isolated notebook compute using JupyterHub on Kubernetes.

## Goals

* Provide notebook compute in isolated pods with per-tenant boundaries.
* Enforce CPU/memory quotas and controlled storage mounts.
* Capture notebook execution lifecycle as auditable events.

## Platform constraints

* Notebook control plane: **JupyterHub**.
* Spawner model: **KubeSpawner**.
* One runtime pod per active notebook user/session.

## Isolation model

* Notebook pod receives tenant context at spawn time.
* Pod mounts only tenant-authorized storage locations.
* Cross-tenant volumes, secrets, and service credentials are not exposed.
* Namespace/resource policies enforce tenant limits and deny privilege escalation.

## Execution lifecycle events

Emit events for:

* notebook session started
* notebook session terminated
* kernel execution requested/completed (where instrumented)
* resource-limit termination

Each event includes tenant id, user id, correlation id, and timestamp.

## Non-goals (this increment)

* Arbitrary cross-tenant shared notebook workspaces.
* Full notebook marketplace/package governance.

## API and events (implemented scaffold slice)

Endpoints:

* `GET/POST /api/v1/notebooks/workspaces`
* `POST /api/v1/notebooks/workspaces/<workspace_id>/sessions`
* `GET /api/v1/notebooks/sessions`
* `POST /api/v1/notebooks/sessions/<session_id>/terminate`
* `POST /api/v1/notebooks/sessions/<session_id>/executions`
* `POST /api/v1/notebooks/executions/<execution_id>/complete`

Events:

* `notebook.workspace.created`
* `notebook.session.started`
* `notebook.session.terminated`
* `notebook.resource_limit.terminated`
* `notebook.execution.requested`
* `notebook.execution.completed`
