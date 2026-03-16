# Data privacy management (design note)

This note defines a privacy-focused increment for Mtafiti centered on tenant-scoped handling of lawful basis, consent state, and privacy actions across metadata and governance flows.

## Goals

* Model privacy-relevant metadata in a way that remains tenant-scoped and auditable.
* Keep privacy checks composable with existing policy, retention, and access-request conventions.
* Define a minimal lifecycle for privacy actions (request, decision, execution, evidence).

## Proposed model (incremental)

Add optional privacy fields on governed assets and related governance records:

* `privacy_profile_id`: stable reference to privacy handling profile.
* `lawful_basis`: e.g. `contract`, `legal_obligation`, `consent`, `legitimate_interest`.
* `consent_required`: boolean indicating whether explicit consent is required for intended processing.
* `consent_state`: `unknown`, `granted`, `withdrawn`, `expired`.
* `privacy_flags`: optional tags such as `contains_pii`, `contains_phi`, `restricted_transfer`.

## Lifecycle conventions

* Privacy profile changes should follow a review path similar to governance workflow conventions.
* Consent changes should produce immutable audit events and timestamped state transitions.
* Withdrawn/expired consent should trigger downstream handling hooks:
  * policy re-evaluation for access and processing rules
  * retention/erasure workflow decisioning
  * stewardship queue assignment when manual remediation is required

## API and events (incremental direction)

* API (future):
  * `POST /api/v1/privacy/profiles`
  * `PATCH /api/v1/privacy/profiles/<privacy_profile_id>`
  * `POST /api/v1/privacy/consent-events`
* Events:
  * `privacy.profile.created`
  * `privacy.profile.updated`
  * `privacy.consent.changed`
  * `privacy.action.required`

## Implemented scaffold baseline

Current scaffold implementation includes:

* `GET/POST /api/v1/privacy/profiles`
* `GET/PATCH /api/v1/privacy/profiles/<privacy_profile_id>`
* `GET/POST /api/v1/privacy/consent-events`
* `GET/POST /api/v1/privacy/actions`
* `POST /api/v1/privacy/actions/<action_id>/decision`
* `POST /api/v1/privacy/actions/<action_id>/execute`

Behavior implemented:

* tenant-scoped privacy profiles with lawful basis, consent requirements, consent state, and privacy flags
* immutable consent events with profile state synchronization
* consent withdrawn/expired integration hooks that create privacy action records for:
  * `policy.re_evaluate`
  * `retention.review`
  * `stewardship.triage`
* privacy action lifecycle states `requested|approved|rejected|executed` with decision and execution evidence capture
* privacy events and audit conventions for profile, consent, and action lifecycle transitions

## Non-goals (this increment)

* Jurisdiction-specific legal interpretation automation.
* Full DLP/content inspection implementation.
* Cross-tenant data movement controls beyond current tenant-isolation boundaries.
