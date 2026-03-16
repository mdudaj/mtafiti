# API change communication and deprecation checklist

This checklist standardizes how Mtafiti communicates API changes so client teams can adopt updates without surprises.

## When to run this checklist

Run this checklist for any API change that affects:

* Request or response payload shape
* Validation behavior and error codes
* Supported headers/query parameters
* Endpoint lifecycle (new, deprecated, removed)

## Required communication package

1. **OpenAPI update**
   * Update `docs/openapi.yaml` in the same change.
   * Ensure the OpenAPI drift gate passes in CI.
2. **Contract safety tests**
   * Add or update contract regression tests under `src/tests/test_api_versioning_contracts.py`.
   * Cover critical stable response fields for affected endpoints.
3. **Client-facing release notes**
   * Describe what changed, why, and who is affected.
   * Include before/after examples for payload or behavior differences.
4. **Migration notes**
   * Provide explicit upgrade actions (field additions, renamed semantics, fallback behavior).
   * Link affected roles/teams and expected rollout order.

## Deprecation checklist (major-version safe)

1. Mark the endpoint/field as deprecated in docs and release notes.
2. Keep deprecated behavior functional for the lifetime of the major API path.
3. Publish a target removal milestone and replacement guidance.
4. Reconfirm compatibility tests for the active major path before each release.
5. Remove only in a new major path (for example, `/api/v2/...`) with migration guidance published in advance.
