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

    vocabulary = client.post(
        "/api/v1/lims/metadata/vocabularies",
        data=json.dumps(
            {
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

    age_field = client.post(
        "/api/v1/lims/metadata/field-definitions",
        data=json.dumps(
            {
                "name": "Age",
                "code": "age",
                "field_type": "integer",
                "help_text": "Participant age in years",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert age_field.status_code == 201

    consent_field = client.post(
        "/api/v1/lims/metadata/field-definitions",
        data=json.dumps(
            {
                "name": "Consent received",
                "code": "consent_received",
                "field_type": "boolean",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert consent_field.status_code == 201

    outcome_field = client.post(
        "/api/v1/lims/metadata/field-definitions",
        data=json.dumps(
            {
                "name": "Outcome",
                "code": "outcome",
                "field_type": "choice",
                "vocabulary_id": vocabulary_id,
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert outcome_field.status_code == 201

    notes_field = client.post(
        "/api/v1/lims/metadata/field-definitions",
        data=json.dumps(
            {
                "name": "Notes",
                "code": "notes",
                "field_type": "long_text",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert notes_field.status_code == 201

    schema = client.post(
        "/api/v1/lims/metadata/schemas",
        data=json.dumps(
            {
                "name": "DBS accessioning",
                "code": "dbs-accessioning",
                "description": "Configurable metadata captured during DBS accessioning.",
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert schema.status_code == 201
    schema_id = schema.json()["id"]

    version = client.post(
        f"/api/v1/lims/metadata/schemas/{schema_id}/versions",
        data=json.dumps(
            {
                "change_summary": "Initial draft",
                "fields": [
                    {
                        "field_definition_id": age_field.json()["id"],
                        "required": True,
                        "validation_rules": {"min": 0, "max": 120},
                    },
                    {
                        "field_definition_id": consent_field.json()["id"],
                        "required": True,
                    },
                    {
                        "field_definition_id": outcome_field.json()["id"],
                        "required": True,
                        "condition": {
                            "field": "consent_received",
                            "operator": "equals",
                            "value": True,
                        },
                    },
                    {
                        "field_definition_id": notes_field.json()["id"],
                        "validation_rules": {"max_length": 50},
                    },
                ],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="lims.admin",
    )
    assert version.status_code == 201
    version_id = version.json()["id"]

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
