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


@pytest.mark.django_db(transaction=True)
def test_lims_metadata_domain_supports_vocabularies_versions_bindings_and_validation(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host = _create_lims_host(client, "tenant-metadata")

    denied = client.post(
        "/api/v1/lims/metadata/vocabularies",
        data=json.dumps({"name": "Outcome", "code": "outcome"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert denied.status_code == 403

    domain = client.post(
        "/api/v1/lims/metadata/vocabulary-domains",
        data=json.dumps(
            {
                "name": "Workflow",
                "code": "workflow",
                "description": "Workflow decisions and route controls.",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert domain.status_code == 201
    domain_id = domain.json()["id"]

    vocabulary = client.post(
        "/api/v1/lims/metadata/vocabularies",
        data=json.dumps(
            {
                "domain_id": domain_id,
                "name": "Outcome",
                "code": "outcome",
                "items": [
                    {"value": "positive", "label": "Positive", "sort_order": 1},
                    {"value": "negative", "label": "Negative", "sort_order": 2},
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert vocabulary.status_code == 201
    vocabulary_id = vocabulary.json()["id"]
    assert vocabulary.json()["domain_code"] == "workflow"

    domain_list = client.get(
        "/api/v1/lims/metadata/vocabulary-domains?search=work",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert domain_list.status_code == 200
    assert domain_list.json()["items"][0]["code"] == "workflow"

    filtered_vocabularies = client.get(
        "/api/v1/lims/metadata/vocabularies?domain_code=workflow&search=posit",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert filtered_vocabularies.status_code == 200
    assert filtered_vocabularies.json()["items"][0]["code"] == "outcome"

    item_search = client.get(
        f"/api/v1/lims/metadata/vocabularies/{vocabulary_id}/items?search=neg&limit=1",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert item_search.status_code == 200
    assert item_search.json()["count"] == 1
    assert item_search.json()["items"][0]["value"] == "negative"
    assert item_search.json()["has_more"] is False

    schema = client.post(
        "/api/v1/lims/metadata/schemas",
        data=json.dumps(
            {
                "name": "DBS accessioning",
                "code": "dbs-accessioning",
                "description": "Configurable metadata captured during DBS accessioning.",
                "purpose": "Receiving intake",
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
    assert version_id

    version = client.put(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions/{version_id}",
        data=json.dumps(
            {
                "fields": [
                    {
                        "name": "Age",
                        "field_key": "age",
                        "field_type": "integer",
                        "help_text": "Participant age in years",
                        "placeholder": "18",
                        "config": {"ui_step": "metadata"},
                        "required": True,
                        "validation_rules": {"min": 0, "max": 120},
                    },
                    {
                        "name": "Consent received",
                        "field_key": "consent_received",
                        "field_type": "boolean",
                        "required": True,
                    },
                    {
                        "name": "Outcome",
                        "field_key": "outcome",
                        "field_type": "choice",
                        "vocabulary_id": vocabulary_id,
                        "config": {"ui_step": "storage"},
                        "required": True,
                        "condition": {
                            "field": "consent_received",
                            "operator": "equals",
                            "value": True,
                        },
                    },
                    {
                        "name": "Notes",
                        "field_key": "notes",
                        "field_type": "long_text",
                        "validation_rules": {"max_length": 50},
                    },
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert version.status_code == 200

    published = client.post(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions/{version_id}/publish",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    binding = client.post(
        "/api/v1/lims/metadata/bindings",
        data=json.dumps(
            {
                "schema_version_id": version_id,
                "target_type": "sample_type",
                "target_key": "dried-blood-spot",
                "target_label": "Dried blood spot",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert binding.status_code == 201
    assert binding.json()["target_type"] == "sample_type"

    listed_bindings = client.get(
        "/api/v1/lims/metadata/bindings?target_type=sample_type&target_key=dried-blood-spot",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert listed_bindings.status_code == 200
    assert listed_bindings.json()["items"][0]["schema_code"] == "dbs-accessioning"

    listed_schemas = client.get(
        f"/api/v1/lims/metadata/schemas/{schema_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert listed_schemas.status_code == 200
    schema_fields = listed_schemas.json()["versions"][0]["fields"]
    assert schema_fields[0]["formbuilder"]["name"] == "age"
    assert schema_fields[0]["formbuilder"]["ui_step"] == "metadata"
    assert schema_fields[0]["name"] == "Age"

    immutable = client.put(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions/{version_id}",
        data=json.dumps({"change_summary": "Should fail", "fields": []}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert immutable.status_code == 400
    assert immutable.json()["error"] == "published_versions_are_immutable"

    next_draft = client.post(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions",
        data=json.dumps(
            {
                "change_summary": "Follow-up draft",
                "source_version_id": version_id,
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert next_draft.status_code == 201
    assert next_draft.json()["status"] == "draft"
    assert len(next_draft.json()["fields"]) == 4
    next_draft_id = next_draft.json()["id"]

    listed_drafts = client.get(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions?status=draft",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert listed_drafts.status_code == 200
    assert [item["id"] for item in listed_drafts.json()["items"]] == [next_draft_id]

    listed_published = client.get(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions?status=published",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert listed_published.status_code == 200
    assert [item["id"] for item in listed_published.json()["items"]] == [version_id]

    published_follow_up = client.post(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions/{next_draft_id}/publish",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert published_follow_up.status_code == 200
    assert published_follow_up.json()["version_number"] == 2

    switched_binding = client.post(
        "/api/v1/lims/metadata/bindings",
        data=json.dumps(
            {
                "schema_version_id": next_draft_id,
                "target_type": "sample_type",
                "target_key": "dried-blood-spot",
                "target_label": "Dried blood spot",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.manager",
    )
    assert switched_binding.status_code == 201
    assert switched_binding.json()["version_number"] == 2

    valid = client.post(
        "/api/v1/lims/metadata/validate",
        data=json.dumps(
            {
                "target_type": "sample_type",
                "target_key": "dried-blood-spot",
                "data": {
                    "age": "18",
                    "consent_received": True,
                    "outcome": "positive",
                    "notes": "received in good condition",
                },
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert valid.status_code == 200
    assert valid.json()["valid"] is True
    assert valid.json()["normalized_data"]["age"] == 18

    invalid = client.post(
        "/api/v1/lims/metadata/validate",
        data=json.dumps(
            {
                "schema_version_id": version_id,
                "data": {
                    "age": 130,
                    "consent_received": True,
                    "outcome": "indeterminate",
                },
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert invalid.status_code == 200
    assert invalid.json()["valid"] is False
    assert {"field": "age", "code": "max"} in invalid.json()["errors"]
    assert {"field": "outcome", "code": "invalid_choice"} in invalid.json()["errors"]

    switched_bindings = client.get(
        "/api/v1/lims/metadata/bindings?target_type=sample_type&target_key=dried-blood-spot",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert switched_bindings.status_code == 200
    assert switched_bindings.json()["items"][0]["version_number"] == 2

    conditional = client.post(
        "/api/v1/lims/metadata/validate",
        data=json.dumps(
            {
                "schema_version_id": version_id,
                "data": {
                    "age": 19,
                    "consent_received": False,
                },
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert conditional.status_code == 200
    assert conditional.json()["valid"] is True


@pytest.mark.django_db(transaction=True)
def test_lims_metadata_domain_is_tenant_scoped(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    client = Client()
    host_a = _create_lims_host(client, "tenant-metadata-a")
    host_b = _create_lims_host(client, "tenant-metadata-b")

    created_schema = client.post(
        "/api/v1/lims/metadata/schemas",
        data=json.dumps({"name": "Storage intake", "code": "storage-intake"}),
        content_type="application/json",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert created_schema.status_code == 201

    list_a = client.get(
        "/api/v1/lims/metadata/schemas",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert list_a.status_code == 200
    assert len(list_a.json()["items"]) == 1

    list_b = client.get(
        "/api/v1/lims/metadata/schemas",
        HTTP_HOST=host_b,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert list_b.status_code == 200
    assert list_b.json()["items"] == []

    provisioned = client.post(
        "/api/v1/lims/metadata/vocabularies/provision-defaults",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert provisioned.status_code == 200
    assert provisioned.json()["created_domains"] >= 1
    assert provisioned.json()["created_vocabularies"] >= 1

    tenant_a_domains = client.get(
        "/api/v1/lims/metadata/vocabulary-domains",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert tenant_a_domains.status_code == 200
    assert {item["code"] for item in tenant_a_domains.json()["items"]} >= {"general", "roles", "consent"}

    tenant_b_domains = client.get(
        "/api/v1/lims/metadata/vocabulary-domains",
        HTTP_HOST=host_b,
        HTTP_X_USER_ROLES="lims.operator",
    )
    assert tenant_b_domains.status_code == 200
    assert {item["code"] for item in tenant_b_domains.json()["items"]} == {"general"}

    fallback_vocabulary = client.post(
        "/api/v1/lims/metadata/vocabularies",
        data=json.dumps(
            {
                "name": "Priority",
                "code": "priority",
                "items": [{"value": "routine", "label": "Routine"}],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host_a,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert fallback_vocabulary.status_code == 201
    assert fallback_vocabulary.json()["domain_code"] == "general"
