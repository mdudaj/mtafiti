import json
import uuid

import pytest
from django.test import Client


def _create_lims_host(client: Client, route_slug: str) -> str:
    control_host = "control.example"
    created_tenant = client.post(
        "/api/v1/tenants",
        data=json.dumps(
            {
                "name": f"Tenant {uuid.uuid4().hex[:6]}",
                "domain": f"tenant-{uuid.uuid4().hex[:6]}.example",
            }
        ),
        content_type="application/json",
        HTTP_HOST=control_host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert created_tenant.status_code == 201
    tenant_id = created_tenant.json()["id"]
    created_route = client.post(
        "/api/v1/tenants/services",
        data=json.dumps(
            {
                "tenant_id": tenant_id,
                "service_key": "lims",
                "tenant_slug": route_slug,
                "base_domain": "mtafiti.apps.nimr.or.tz",
            }
        ),
        content_type="application/json",
        HTTP_HOST=control_host,
        HTTP_X_USER_ROLES="tenant.admin",
    )
    assert created_route.status_code == 201
    return created_route.json()["domain"]


def _create_published_schema(client: Client, host: str) -> str:
    domain = client.post(
        "/api/v1/lims/metadata/vocabulary-domains",
        data=json.dumps({"name": "Workflow", "code": "workflow"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert domain.status_code == 201
    vocabulary = client.post(
        "/api/v1/lims/metadata/vocabularies",
        data=json.dumps(
            {
                "domain_id": domain.json()["id"],
                "name": "Outcome",
                "code": "outcome",
                "items": [
                    {"value": "accept", "label": "Accept", "sort_order": 1},
                    {"value": "reject", "label": "Reject", "sort_order": 2},
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert vocabulary.status_code == 201
    schema = client.post(
        "/api/v1/lims/metadata/schemas",
        data=json.dumps(
            {
                "name": "Accession task schema",
                "code": "accession-task-schema",
                "description": "Schema used for form engine bootstrap tests.",
                "purpose": "Workflow task capture",
                "change_summary": "Initial draft",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert schema.status_code == 201
    schema_id = schema.json()["id"]
    version_id = schema.json()["draft_version_id"]
    updated = client.put(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions/{version_id}",
        data=json.dumps(
            {
                "fields": [
                    {
                        "name": "Subject identifier",
                        "field_key": "subject_identifier",
                        "field_type": "text",
                        "required": True,
                        "config": {"ui_step": "intake"},
                    },
                    {
                        "name": "Outcome",
                        "field_key": "outcome",
                        "field_type": "choice",
                        "vocabulary_id": vocabulary.json()["id"],
                        "required": True,
                        "config": {"ui_step": "qc"},
                    },
                ]
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert updated.status_code == 200
    published = client.post(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions/{version_id}/publish",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert published.status_code == 200
    return version_id


@pytest.mark.django_db(transaction=True)
def test_lims_form_engine_bootstraps_publishes_and_clones_from_metadata_schema(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-form-engine")
    schema_version_id = _create_published_schema(client, host)

    created = client.post(
        "/api/v1/lims/form-packages",
        data=json.dumps(
            {
                "name": "Sample accession package",
                "code": "sample-accession-package",
                "description": "Compiler-owned package bootstrapped from metadata.",
                "purpose": "Accessioning",
                "module_scope": "shared",
                "change_summary": "Initial draft",
                "source_schema_version_id": schema_version_id,
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert created.status_code == 201
    payload = created.json()
    package_id = payload["id"]
    version_id = payload["draft_version_id"]
    version = payload["versions"][0]
    assert version["source_schema_version_id"] == schema_version_id
    assert [item["section_key"] for item in version["sections"]] == ["intake", "qc"]
    assert len(version["items"]) == 2
    assert len(version["choice_lists"]) == 1
    assert version["source_artifacts"][0]["artifact_metadata"]["source_kind"] == "metadata_schema_version"

    published = client.post(
        f"/api/v1/lims/form-packages/{package_id}/versions/{version_id}/publish",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert published.status_code == 200
    published_payload = published.json()
    assert published_payload["status"] == "published"
    assert published_payload["compiled_projection"]["package_code"] == "sample-accession-package"
    assert len(published_payload["compiled_projection"]["sections"]) == 2
    assert len(published_payload["compiled_projection"]["choice_lists"]) == 1
    assert published_payload["compiler_diagnostics"][0]["code"] == "compiled_projection_ready"

    immutable = client.put(
        f"/api/v1/lims/form-packages/{package_id}/versions/{version_id}",
        data=json.dumps({"change_summary": "Should fail"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert immutable.status_code == 400
    assert immutable.json()["error"] == "published_versions_are_immutable"

    cloned = client.post(
        f"/api/v1/lims/form-packages/{package_id}/versions",
        data=json.dumps({"source_version_id": version_id, "change_summary": "Follow-up draft"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert cloned.status_code == 201
    assert cloned.json()["status"] == "draft"
    assert len(cloned.json()["sections"]) == 2
    assert len(cloned.json()["items"]) == 2


@pytest.mark.django_db(transaction=True)
def test_lims_form_engine_surfaces_publish_validation_diagnostics(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-form-engine-validation")

    created = client.post(
        "/api/v1/lims/form-packages",
        data=json.dumps(
            {
                "name": "Broken package",
                "code": "broken-package",
                "description": "Used to verify compiler diagnostics.",
                "purpose": "Validation",
                "change_summary": "Initial draft",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert created.status_code == 201
    package_id = created.json()["id"]
    version_id = created.json()["draft_version_id"]

    updated = client.put(
        f"/api/v1/lims/form-packages/{package_id}/versions/{version_id}",
        data=json.dumps(
            {
                "sections": [
                    {
                        "section_key": "intake",
                        "oid": "SEC.INTAKE",
                        "title": "Intake",
                    }
                ],
                "items": [
                    {
                        "item_key": "outcome",
                        "oid": "ITEM.OUTCOME",
                        "section_key": "intake",
                        "question_text": "Outcome",
                        "field_type": "choice",
                        "required": True,
                    }
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert updated.status_code == 200

    published = client.post(
        f"/api/v1/lims/form-packages/{package_id}/versions/{version_id}/publish",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert published.status_code == 400
    assert published.json()["error"] == "form_package_validation_failed"
    assert published.json()["details"][0]["code"] == "choice_list_required"

    detail = client.get(
        f"/api/v1/lims/form-packages/{package_id}/versions/{version_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "draft"
    assert detail.json()["compiler_diagnostics"][0]["code"] == "choice_list_required"
