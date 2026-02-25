# Data privacy management (design note)

This note defines a privacy-focused increment for EDMP centered on tenant-scoped handling of lawful basis, consent state, and privacy actions across metadata and governance flows.

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

## Non-goals (this increment)

* Jurisdiction-specific legal interpretation automation.
* Full DLP/content inspection implementation.
* Cross-tenant data movement controls beyond current tenant-isolation boundaries.
