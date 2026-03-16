# Project membership and invitations

Projects support role-based member assignment and invitation workflows within a tenant.

## Supported project roles

* `principal_investigator`
* `researcher`
* `data_manager`

## Invitation flow

1. Project admins call `POST /api/v1/projects/{project_id}/members/invite` with `email` and `role`.
2. If the user is already known in-tenant (existing active membership), Mtafiti creates an in-app notification and directly upserts project membership.
3. If the user is new, Mtafiti creates a pending invitation with an expiring one-time token and emits an email-channel notification payload containing an invite link.
4. Invitees accept via `POST /api/v1/projects/invitations/accept` with the token, which activates membership and marks the invitation as accepted.
5. Operators can revoke and resend invites via `POST /api/v1/projects/invitations/{invitation_id}/revoke` and `POST /api/v1/projects/invitations/{invitation_id}/resend`.

## Guardrails

* Invitation tokens are single-use and can expire.
* Invitation tokens are stored as hashes at rest; resend rotates token material.
* Invitation acceptance is bounded by maximum attempt policy.
* Invitation acceptance rejects missing, invalid, expired, or non-pending tokens.
* Invite/accept operations emit project invitation/member event and audit records.
