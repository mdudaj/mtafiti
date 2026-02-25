# Audit events design notes

This note defines a minimal, tenant-safe audit increment for EDMP.

## Goals

* Emit consistent audit events for all mutating API actions.
* Preserve tenant isolation in routing keys and payload metadata.
* Keep event publishing optional (`RABBITMQ_URL` unset => no-op) so local/dev remains simple.

## Scope (initial)

Emit audit/domain events for:

* tenant create (`tenant.created`)
* asset create/update/delete (`asset.created`, `asset.updated`, `asset.deleted` when delete exists)
* lineage edge upsert (`lineage.edge.upserted`)
* policy changes (`policy.created`, `policy.updated`, `policy.deleted` when policy API exists)

## Event shape

Reuse the existing envelope in `docs/events.md` and include domain-specific `data`:

* `action`: canonical event type (for example, `asset.updated`)
* `resource.type` and `resource.id`
* `actor.user_id` (from `X-User-Id` in current scaffold)
* `changes` (optional; key-level diffs for updates)

## Implementation notes

1. Emit from API handlers only after successful mutation/commit.
2. Use tenant-aware routing keys: `<tenant_schema>.<domain>.<event>`.
3. Keep payloads metadata-first; avoid embedding large resource blobs.
4. Add task-originated audit events later using the same envelope and correlation id propagation.

## Non-goals (initial)

* Read/query auditing for all endpoints.
* Long-term audit retention/indexing strategy.
* Cross-tenant/global audit query APIs.
