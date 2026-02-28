# Identity lifecycle and membership operations

This increment adds tenant-scoped identity lifecycle primitives to support project collaboration workflows.

## User directory APIs

* `POST /api/v1/users` creates user profiles (`active`, `invited`, `disabled`).
* `GET /api/v1/users` lists users with optional status/email filters.
* `GET|PATCH /api/v1/users/{user_id}` reads or updates profile state.

## Membership lifecycle APIs

* `GET /api/v1/projects/{project_id}/members` lists project members.
* `POST /api/v1/projects/{project_id}/members/{membership_id}/lifecycle` supports:
  * `change_role` (requires `role`)
  * `revoke`
  * `reactivate`

Every lifecycle change records role/status history and emits event + audit payloads for traceability.

## Invite integration behavior

* Existing users are detected from the user directory and receive in-app notifications.
* New invitees receive one-time login links and are created as `invited` profiles.
* Accepting an invitation activates membership and user profile state.
