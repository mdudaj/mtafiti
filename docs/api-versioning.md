# API versioning and deprecation policy

Mtafiti keeps stable APIs under `/api/v1/...` and treats `v1` as the current compatibility baseline.

## Versioning strategy

* **Path majoring**: breaking changes require a new major path (`/api/v2/...`).
* **Additive-first changes in v1**: new optional fields and new endpoints are allowed in `v1`; existing response fields are not removed or renamed.
* **Negotiation header**: clients may send `X-API-Version`; currently only `v1` is supported.
* **Response header**: API responses include `X-API-Version: v1`.

## Deprecation policy

* Deprecations are announced in release notes and docs before removal in a new major version.
* Deprecated fields/endpoints remain functional for the full lifetime of their major version.
* Removals or semantic breaks are only introduced in a new major path.

## Compatibility checks

* Contract regression tests in `src/tests/test_api_versioning_contracts.py` protect critical response keys for stable endpoints.
* OpenAPI drift checks in `.github/scripts/check_openapi_contract.py` fail CI when critical implemented routes or schemas are missing from `docs/openapi.yaml`.
* Tests also enforce that unsupported `X-API-Version` values are rejected with `unsupported_api_version`.

## Migration and communication process

When introducing a new major API version:

1. Publish migration guidance with old/new request-response examples.
2. Keep prior major version active during a documented transition window.
3. Announce deprecation/removal milestones in docs and release notes.
4. Update `docs/openapi.yaml` and run compatibility tests for both supported majors during overlap.
5. Follow the shared [API change communication and deprecation checklist](api-change-management.md).
