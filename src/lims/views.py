import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify

from core.identity import request_roles, roles_enforced

from .permissions import has_lims_permission, permission_summary_for_roles, require_lims_permission
from .models import (
    AccessioningManifest,
    AccessioningManifestItem,
    Biospecimen,
    BiospecimenPool,
    BiospecimenType,
    Country,
    District,
    Lab,
    MetadataFieldDefinition,
    MetadataSchema,
    MetadataSchemaBinding,
    MetadataSchemaField,
    MetadataSchemaVersion,
    MetadataVocabulary,
    MetadataVocabularyDomain,
    MetadataVocabularyItem,
    PlateLayoutTemplate,
    Postcode,
    ProcessingBatch,
    ReceivingDiscrepancy,
    ReceivingEvent,
    Region,
    Site,
    Street,
    Study,
    TanzaniaAddressSyncRun,
    Ward,
)
from .services import (
    accessioning_report,
    AccessioningError,
    allocate_biospecimen_identifiers,
    BatchPlateError,
    BiospecimenTransitionError,
    create_receiving_discrepancy,
    create_aliquots,
    create_processing_batch,
    create_processing_batch_worksheet_job,
    create_pool,
    generate_manifest_identifier,
    get_default_metadata_vocabulary_domain,
    processing_batch_worksheet,
    provision_default_metadata_vocabularies,
    receive_manifest_item,
    receive_single_biospecimen,
    resolve_schema_version_for_binding,
    submit_manifest,
    sync_run_to_dict,
    transition_processing_batch,
    transition_biospecimen,
    transition_pool,
    validate_metadata_payload,
)
from .tasks import sync_tanzania_address_run


def _user_context(request) -> dict[str, object]:
    user_id = (request.headers.get('X-User-Id') or 'anonymous').strip()
    raw_roles = (request.headers.get('X-User-Roles') or '').strip()
    roles = sorted({role.strip() for role in raw_roles.split(',') if role.strip()})
    tenant = getattr(request, 'tenant', None)
    return {
        'user_id': user_id,
        'roles': roles,
        'tenant_schema': getattr(tenant, 'schema_name', 'public'),
    }


def _ui_feedback_context(request) -> dict[str, object]:
    message = (request.GET.get("ui_message") or "").strip()
    error = (request.GET.get("ui_error") or "").strip()
    return {
        "ui_message": message,
        "ui_error": error.lower() in {"1", "true", "yes"},
    }


def _can_view_operations(request) -> bool:
    if not roles_enforced():
        return True
    return bool(
        set(request_roles(request))
        & {"catalog.reader", "catalog.editor", "policy.admin", "tenant.admin", "lims.operator", "lims.manager", "lims.qa", "lims.admin"}
    )


def _has_permission(request, permission_key: str) -> bool:
    if not roles_enforced():
        return True
    return has_lims_permission(request_roles(request), permission_key)


def _lims_navigation(request, active_key: str) -> dict[str, object]:
    links = []
    candidates = [
        ("lims-dashboard", "Dashboard", "dashboard", "/lims/", "lims.dashboard.view"),
        ("lims-reference", "Reference", "globe_location_pin", "/lims/reference/", "lims.reference.view"),
        ("lims-metadata", "Metadata", "schema", "/lims/metadata/", "lims.metadata.view"),
        ("lims-biospecimens", "Biospecimens", "biotech", "/lims/biospecimens/", "lims.artifact.view"),
        ("lims-receiving", "Receiving", "inventory_2", "/lims/receiving/", "lims.artifact.view"),
        ("lims-processing", "Processing", "science", "/lims/processing/", "lims.artifact.view"),
    ]
    for key, label, icon, href, permission_key in candidates:
        if _has_permission(request, permission_key):
            links.append(
                {
                    "key": key,
                    "label": label,
                    "icon": icon,
                    "href": href,
                    "is_active": key == active_key,
                }
            )
    return {
        "can_view_operations": _can_view_operations(request),
        "lims_links": links,
    }


def _page_payload_base(request, *, active_key: str, title: str, summary: str, kicker: str) -> dict[str, object]:
    user_context = _user_context(request)
    return {
        "service_key": "lims",
        "tenant_schema": user_context["tenant_schema"],
        "user_context": user_context,
        "navigation": _lims_navigation(request, active_key),
        "capabilities": {
            "can_view_reference": _has_permission(request, "lims.reference.view"),
            "can_manage_reference": _has_permission(request, "lims.reference.manage"),
            "can_view_metadata": _has_permission(request, "lims.metadata.view"),
            "can_manage_metadata": _has_permission(request, "lims.metadata.manage"),
            "can_view_artifacts": _has_permission(request, "lims.artifact.view"),
            "can_manage_artifacts": _has_permission(request, "lims.artifact.manage"),
            "can_execute_tasks": _has_permission(request, "lims.workflow.execute"),
            "can_approve_tasks": _has_permission(request, "lims.workflow.approve"),
        },
        "page": {
            "page_title": title,
            "page_summary": summary,
            "topbar_title": title,
            "topbar_subtitle": summary,
            "kicker": kicker,
            "section_label": "LIMS",
        },
        "cards": {},
    }


def _page_context(request, *, active_nav: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "active_nav": active_nav,
        "payload": payload,
        **_ui_feedback_context(request),
    }


def _dashboard_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-dashboard",
        title="Laboratory operations workspace",
        summary="Use tenant-scoped reference, metadata, accessioning, and processing tools from one admin-style shell.",
        kicker="LIMS overview",
    )
    labs_count = Lab.objects.count()
    schema_count = MetadataSchema.objects.count()
    specimen_count = Biospecimen.objects.count()
    manifest_count = AccessioningManifest.objects.count()
    batch_count = ProcessingBatch.objects.count()
    payload["cards"] = {
        "labs": labs_count,
        "schemas": schema_count,
        "biospecimens": specimen_count,
        "manifests": manifest_count,
        "batches": batch_count,
    }
    payload["launchpad"] = [
        {
            "title": "Reference data",
            "description": "Manage labs, studies, sites, and address sync runs for the tenant.",
            "href": "/lims/reference/",
            "status": "ready" if payload["capabilities"]["can_view_reference"] else "restricted",
        },
        {
            "title": "Metadata schemas",
            "description": "Define vocabularies, fields, schemas, and published bindings for configurable forms.",
            "href": "/lims/metadata/",
            "status": "ready" if payload["capabilities"]["can_view_metadata"] else "restricted",
        },
        {
            "title": "Biospecimens",
            "description": "Register sample types, create specimens, and assemble pools for downstream workflow steps.",
            "href": "/lims/biospecimens/",
            "status": "ready" if payload["capabilities"]["can_view_artifacts"] else "restricted",
        },
        {
            "title": "Receiving",
            "description": "Receive single samples, track manifests, and capture discrepancy workflows.",
            "href": "/lims/receiving/",
            "status": "ready" if payload["capabilities"]["can_view_artifacts"] else "restricted",
        },
        {
            "title": "Processing",
            "description": "Create plate-based batches, review assignments, and trigger worksheet print jobs.",
            "href": "/lims/processing/",
            "status": "ready" if payload["capabilities"]["can_view_artifacts"] else "restricted",
        },
    ]
    payload["recent_manifests"] = [
        _accessioning_manifest_to_dict(item)
        for item in AccessioningManifest.objects.select_related("sample_type").order_by("-created_at")[:5]
    ]
    payload["recent_batches"] = [
        _processing_batch_to_dict(item)
        for item in ProcessingBatch.objects.select_related("sample_type").order_by("-created_at")[:5]
    ]
    payload["recent_specimens"] = [
        _biospecimen_to_dict(item)
        for item in Biospecimen.objects.select_related("sample_type").order_by("-created_at")[:5]
    ]
    return payload


def _reference_launchpad_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-reference",
        title="Reference and geography",
        summary="Choose a focused reference-data task, then complete it on a dedicated single-action page.",
        kicker="Reference operations",
    )
    payload["cards"] = {
        "labs": Lab.objects.count(),
        "studies": Study.objects.count(),
        "sites": Site.objects.count(),
        "sync_runs": TanzaniaAddressSyncRun.objects.count(),
    }
    payload["labs"] = [_lab_to_dict(item) for item in Lab.objects.order_by("name")[:10]]
    payload["studies"] = [_study_to_dict(item) for item in Study.objects.select_related("lead_lab").order_by("name")[:10]]
    payload["sites"] = [
        _site_to_dict(item)
        for item in Site.objects.select_related("study", "lab").prefetch_related("studies").order_by("name")[:10]
    ]
    payload["sync_runs"] = [sync_run_to_dict(item) for item in TanzaniaAddressSyncRun.objects.order_by("-created_at")[:5]]
    payload["actions"] = [
        {
            "title": "Create lab",
            "description": "Register one tenant lab at a time using a dedicated lab form.",
            "href": "/lims/reference/labs/create/",
            "icon": "add_business",
        },
        {
            "title": "Create study",
            "description": "Create one study and optionally attach its lead lab.",
            "href": "/lims/reference/studies/create/",
            "icon": "schema",
        },
        {
            "title": "Create site",
            "description": "Register one field or collection site and link it to study and lab selectors.",
            "href": "/lims/reference/sites/create/",
            "icon": "location_city",
        },
        {
            "title": "Run geography sync",
            "description": "Start the Tanzania-backed geography import from a single sync action page.",
            "href": "/lims/reference/address-sync/",
            "icon": "sync",
        },
    ]
    return payload


def _reference_create_lab_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-reference",
        title="Create lab",
        summary="Capture one tenant lab at a time without mixing this form with other setup actions.",
        kicker="Reference setup",
    )
    payload["address_country"] = Country.objects.filter(code="TZ").first()
    return payload


def _reference_create_study_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-reference",
        title="Create study",
        summary="Create one study record and optionally assign a lead lab for routing and receiving defaults.",
        kicker="Reference setup",
    )
    payload["lab_options"] = [_model_to_option(item) for item in Lab.objects.order_by("name")]
    return payload


def _reference_create_site_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-reference",
        title="Create site",
        summary="Register one site at a time so downstream receiving and biospecimen forms stay focused.",
        kicker="Reference setup",
    )
    payload["study_options"] = [_model_to_option(item) for item in Study.objects.order_by("name")]
    payload["lab_options"] = [_model_to_option(item) for item in Lab.objects.order_by("name")]
    payload["address_country"] = Country.objects.filter(code="TZ").first()
    return payload


def _reference_address_sync_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-reference",
        title="Run geography sync",
        summary="Queue one geography sync run at a time from a dedicated action page.",
        kicker="Reference setup",
    )
    payload["sync_runs"] = [sync_run_to_dict(item) for item in TanzaniaAddressSyncRun.objects.order_by("-created_at")[:8]]
    return payload


def _metadata_launchpad_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-metadata",
        title="Metadata configuration",
        summary="Choose a focused metadata task, then complete it on a dedicated single-action page.",
        kicker="Configurable metadata",
    )
    payload["cards"] = {
        "domains": MetadataVocabularyDomain.objects.count(),
        "vocabularies": MetadataVocabulary.objects.count(),
        "versions": MetadataSchemaVersion.objects.count(),
        "schemas": MetadataSchema.objects.count(),
        "bindings": MetadataSchemaBinding.objects.count(),
    }
    payload["vocabularies"] = [
        _vocabulary_to_dict(item)
        for item in MetadataVocabulary.objects.select_related("domain").prefetch_related("items").order_by("name")[:8]
    ]
    payload["draft_versions"] = [
        _schema_version_to_dict(item)
        for item in MetadataSchemaVersion.objects.select_related("schema").prefetch_related("fields__vocabulary").filter(
            status=MetadataSchemaVersion.Status.DRAFT
        ).order_by("-updated_at")[:10]
    ]
    payload["schemas"] = [
        _schema_to_dict(item)
        for item in MetadataSchema.objects.prefetch_related(
            "versions__fields__vocabulary",
            "versions__schema",
        ).order_by("name")[:6]
    ]
    payload["bindings"] = [
        _schema_binding_to_dict(item)
        for item in MetadataSchemaBinding.objects.select_related("schema_version__schema").order_by("target_type", "target_key")[:10]
    ]
    payload["actions"] = [
        {
            "title": "Create vocabulary",
            "description": "Seed one controlled vocabulary from a dedicated create form.",
            "href": "/lims/metadata/vocabularies/create/",
            "icon": "list_alt",
        },
        {
            "title": "Create form + draft",
            "description": "Define form metadata first, then build the initial draft version with version-owned fields.",
            "href": "/lims/metadata/schemas/create/",
            "icon": "schema",
        },
        {
            "title": "Create binding",
            "description": "Attach one published schema version to one sample type or workflow target.",
            "href": "/lims/metadata/bindings/create/",
            "icon": "link",
        },
        {
            "title": "Publish version",
            "description": "Promote one draft schema version without mixing publishing with binding creation.",
            "href": "/lims/metadata/versions/publish/",
            "icon": "publish",
        },
    ]
    return payload


def _metadata_create_vocabulary_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-metadata",
        title="Create vocabulary",
        summary="Seed one controlled vocabulary and its initial items on a dedicated setup page.",
        kicker="Metadata setup",
    )
    payload["domain_options"] = [_model_to_option(item) for item in MetadataVocabularyDomain.objects.filter(is_active=True).order_by("name")]
    return payload


def _metadata_create_field_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-metadata",
        title="Create field definition",
        summary="Define one reusable field, including help text, placeholder, defaults, and wizard-step placement.",
        kicker="Metadata setup",
    )
    payload["field_type_options"] = [{"value": value, "label": label} for value, label in MetadataFieldDefinition.FieldType.choices]
    payload["ui_step_options"] = [
        {"value": "metadata", "label": "Wizard metadata step"},
        {"value": "storage", "label": "Wizard storage step"},
    ]
    payload["vocabulary_options"] = [_model_to_option(item) for item in MetadataVocabulary.objects.order_by("name")]
    return payload


def _metadata_create_schema_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-metadata",
        title="Create form and draft version",
        summary="Step 1 creates the form definition and initial draft. Step 2 edits fields that belong directly to that draft version.",
        kicker="Metadata setup",
    )
    payload["field_type_options"] = [{"value": value, "label": label} for value, label in MetadataFieldDefinition.FieldType.choices]
    payload["ui_step_options"] = [
        {"value": "metadata", "label": "Wizard metadata step"},
        {"value": "storage", "label": "Wizard storage step"},
    ]
    payload["vocabulary_options"] = [_model_to_option(item) for item in MetadataVocabulary.objects.filter(is_active=True).order_by("name")]
    payload["schema_options"] = [
        {
            "value": str(item.id),
            "label": item.name,
            "code": item.code,
            "draft_version_id": next(
                (str(version.id) for version in item.versions.all() if version.status == MetadataSchemaVersion.Status.DRAFT),
                "",
            ),
        }
        for item in MetadataSchema.objects.prefetch_related("versions").order_by("name")
    ]
    payload["published_version_options"] = [
        {
            "value": str(item.id),
            "label": f"{item.schema.name} v{item.version_number}",
            "schema_id": str(item.schema_id),
        }
        for item in MetadataSchemaVersion.objects.select_related("schema")
        .filter(status=MetadataSchemaVersion.Status.PUBLISHED)
        .order_by("schema__name", "-version_number")
    ]
    payload["binding_target_type_options"] = [
        {"value": value, "label": label} for value, label in MetadataSchemaBinding.TargetType.choices
    ]
    payload["sample_type_options"] = [
        {"value": item.key, "label": item.name}
        for item in BiospecimenType.objects.order_by("name")
    ]
    return payload


def _metadata_create_binding_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-metadata",
        title="Create schema binding",
        summary="Bind one schema version to one target from a dedicated attachment page.",
        kicker="Metadata setup",
    )
    payload["binding_target_type_options"] = [
        {"value": value, "label": label} for value, label in MetadataSchemaBinding.TargetType.choices
    ]
    payload["schema_version_options"] = [
        {
            "value": str(item.id),
            "label": f"{item.schema.code} v{item.version_number} ({item.status})",
            "schema_id": str(item.schema_id),
        }
        for item in MetadataSchemaVersion.objects.select_related("schema")
        .filter(status=MetadataSchemaVersion.Status.PUBLISHED)
        .order_by("schema__name", "-version_number")
    ]
    payload["sample_type_options"] = [
        {"value": item.key, "label": item.name}
        for item in BiospecimenType.objects.order_by("name")
    ]
    return payload


def _metadata_publish_version_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-metadata",
        title="Publish schema version",
        summary="Promote one draft schema version from a single publish form.",
        kicker="Metadata setup",
    )
    payload["schema_version_options"] = [
        {
            "value": str(item.id),
            "label": f"{item.schema.code} v{item.version_number} ({item.status})",
            "schema_id": str(item.schema_id),
        }
        for item in MetadataSchemaVersion.objects.select_related("schema")
        .filter(status=MetadataSchemaVersion.Status.DRAFT)
        .order_by("schema__name", "-version_number")
    ]
    return payload


def _biospecimens_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-biospecimens",
        title="Biospecimen registry",
        summary="Register sample types, create specimens, and monitor pool composition before receiving and batch processing.",
        kicker="Specimen inventory",
    )
    payload["cards"] = {
        "sample_types": BiospecimenType.objects.count(),
        "specimens": Biospecimen.objects.count(),
        "aliquots": Biospecimen.objects.filter(kind=Biospecimen.Kind.ALIQUOT).count(),
        "pools": BiospecimenPool.objects.count(),
    }
    payload["sample_types"] = [_biospecimen_type_to_dict(item) for item in BiospecimenType.objects.order_by("name")[:10]]
    payload["specimens"] = [
        _biospecimen_to_dict(item)
        for item in Biospecimen.objects.select_related("sample_type", "study", "site", "lab").order_by("-created_at")[:10]
    ]
    payload["pools"] = [
        _biospecimen_pool_to_dict(item)
        for item in BiospecimenPool.objects.select_related("sample_type", "study", "site", "lab").order_by("-created_at")[:8]
    ]
    payload["sample_type_options"] = [_model_to_option(item) for item in BiospecimenType.objects.order_by("name")]
    payload["lab_options"] = [_model_to_option(item) for item in Lab.objects.order_by("name")]
    payload["study_options"] = [_model_to_option(item) for item in Study.objects.order_by("name")]
    payload["site_options"] = [_model_to_option(item) for item in Site.objects.order_by("name")]
    payload["specimen_options"] = [
        {"value": str(item.id), "label": f"{item.sample_identifier} ({item.status})"}
        for item in Biospecimen.objects.order_by("-created_at")[:50]
    ]
    return payload


def _receiving_launchpad_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-receiving",
        title="Receiving and accessioning",
        summary="Choose a focused receiving flow, then complete that task on a dedicated one-form page.",
        kicker="Accessioning",
    )
    payload["cards"] = {
        "manifests": AccessioningManifest.objects.count(),
        "received_events": ReceivingEvent.objects.count(),
        "discrepancies": ReceivingDiscrepancy.objects.count(),
        "pending_items": AccessioningManifestItem.objects.filter(status=AccessioningManifestItem.Status.PENDING).count(),
    }
    payload["manifests"] = [
        _accessioning_manifest_to_dict(item)
        for item in AccessioningManifest.objects.select_related("sample_type", "study", "site", "lab").order_by("-created_at")[:10]
    ]
    payload["events"] = [
        _receiving_event_to_dict(item)
        for item in ReceivingEvent.objects.select_related("biospecimen").order_by("-received_at")[:8]
    ]
    payload["discrepancies"] = [
        _receiving_discrepancy_to_dict(item)
        for item in ReceivingDiscrepancy.objects.order_by("-created_at")[:8]
    ]
    payload["actions"] = [
        {
            "title": "Single sample receipt",
            "description": "Capture intake metadata, record a QC accept/reject decision, then log storage or rejection details.",
            "href": "/lims/receiving/single/",
            "icon": "move_to_inbox",
        },
        {
            "title": "Batch manifest receipt",
            "description": "Download an Excel-friendly CSV template, complete receipt/QC/storage columns, and import the batch.",
            "href": "/lims/receiving/batch/",
            "icon": "upload_file",
        },
        {
            "title": "Retrieve from EDC",
            "description": "Specify the lab form, expected sample, and external ID, then process the imported record through QC.",
            "href": "/lims/receiving/edc-import/",
            "icon": "cloud_download",
        },
    ]
    return payload


def _receiving_single_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-receiving",
        title="Receive single specimen",
        summary="Capture initial metadata, complete the first QC decision, then log storage or document a rejection.",
        kicker="Single receipt",
    )
    payload["sample_type_options"] = [
        {"value": str(item.id), "label": item.name, "key": item.key}
        for item in BiospecimenType.objects.order_by("name")
    ]
    payload["study_options"] = [_model_to_option(item) for item in Study.objects.order_by("name")]
    payload["site_options"] = [_model_to_option(item) for item in Site.objects.order_by("name")]
    payload["lab_options"] = [_model_to_option(item) for item in Lab.objects.order_by("name")]
    payload["discrepancy_code_options"] = [
        {"value": value, "label": label} for value, label in ReceivingDiscrepancy.Code.choices
    ]
    return payload


def _receiving_batch_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-receiving",
        title="Receive batch manifest",
        summary="Use one batch import form to load intake metadata, QC outcomes, and storage instructions from a template.",
        kicker="Batch receipt",
    )
    payload["sample_type_options"] = [_model_to_option(item) for item in BiospecimenType.objects.order_by("name")]
    payload["study_options"] = [_model_to_option(item) for item in Study.objects.order_by("name")]
    payload["site_options"] = [_model_to_option(item) for item in Site.objects.order_by("name")]
    payload["lab_options"] = [_model_to_option(item) for item in Lab.objects.order_by("name")]
    payload["discrepancy_code_options"] = [
        {"value": value, "label": label} for value, label in ReceivingDiscrepancy.Code.choices
    ]
    payload["recent_manifests"] = [
        _accessioning_manifest_to_dict(item)
        for item in AccessioningManifest.objects.select_related("sample_type").order_by("-created_at")[:8]
    ]
    return payload


def _receiving_edc_import_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-receiving",
        title="Retrieve metadata from EDC",
        summary="Capture the lab form, expected sample, external ID import target, and QC/storage outcome in one flow.",
        kicker="EDC intake",
    )
    payload["sample_type_options"] = [_model_to_option(item) for item in BiospecimenType.objects.order_by("name")]
    payload["study_options"] = [_model_to_option(item) for item in Study.objects.order_by("name")]
    payload["site_options"] = [_model_to_option(item) for item in Site.objects.order_by("name")]
    payload["lab_options"] = [_model_to_option(item) for item in Lab.objects.order_by("name")]
    payload["discrepancy_code_options"] = [
        {"value": value, "label": label} for value, label in ReceivingDiscrepancy.Code.choices
    ]
    payload["edc_source_options"] = [
        {"value": "redcap", "label": "REDCap"},
        {"value": "odk", "label": "ODK"},
        {"value": "odk-central", "label": "ODK Central"},
    ]
    return payload


def _processing_page_payload(request) -> dict[str, object]:
    payload = _page_payload_base(
        request,
        active_key="lims-processing",
        title="Batch and plate processing",
        summary="Create processing batches, inspect plate layouts, and issue worksheet print jobs for downstream lab execution.",
        kicker="Batch management",
    )
    payload["cards"] = {
        "layouts": PlateLayoutTemplate.objects.count(),
        "batches": ProcessingBatch.objects.count(),
        "draft_batches": ProcessingBatch.objects.filter(status=ProcessingBatch.Status.DRAFT).count(),
        "printed_batches": ProcessingBatch.objects.filter(status=ProcessingBatch.Status.PRINTED).count(),
    }
    payload["layouts"] = [_plate_layout_to_dict(item) for item in PlateLayoutTemplate.objects.order_by("rows", "columns")]
    payload["batches"] = [
        _processing_batch_to_dict(item, include_plates=True)
        for item in ProcessingBatch.objects.select_related("sample_type", "study", "site", "lab")
        .prefetch_related("plates__layout_template", "plates__assignments__biospecimen")
        .order_by("-created_at")[:8]
    ]
    payload["sample_type_options"] = [_model_to_option(item) for item in BiospecimenType.objects.order_by("name")]
    payload["study_options"] = [_model_to_option(item) for item in Study.objects.order_by("name")]
    payload["site_options"] = [_model_to_option(item) for item in Site.objects.order_by("name")]
    payload["lab_options"] = [_model_to_option(item) for item in Lab.objects.order_by("name")]
    payload["layout_options"] = [_model_to_option(item) for item in PlateLayoutTemplate.objects.order_by("rows", "columns")]
    payload["batch_options"] = [
        {"value": str(item.id), "label": f"{item.batch_identifier} ({item.status})"}
        for item in ProcessingBatch.objects.order_by("-created_at")[:50]
    ]
    return payload


def _parse_json_body(request):
    try:
        body = request.body.decode("utf-8") if request.body else ""
        return json.loads(body or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _model_to_option(item, label_attr: str = "name") -> dict[str, str]:
    return {"value": str(item.id), "label": getattr(item, label_attr)}


def _option(value: str, label: str, description: str = "") -> dict[str, str]:
    payload = {"value": value, "label": label}
    if description:
        payload["description"] = description
    return payload


def _address_breadcrumb(*, country=None, region=None, district=None, ward=None, street=None, postcode: str = "", address_line: str = "") -> str:
    parts = []
    if address_line:
        parts.append(address_line)
    if street:
        parts.append(street.name)
    if ward:
        parts.append(ward.name)
    if district:
        parts.append(district.name)
    if region:
        parts.append(region.name)
    if country:
        parts.append(country.name)
    if postcode:
        parts.append(postcode)
    return " / ".join(parts)


def _badge(label: str, tone: str = "info") -> dict[str, str]:
    return {"label": label, "tone": tone}


def _lab_to_dict(lab: Lab) -> dict[str, object]:
    address_breadcrumb = _address_breadcrumb(
        country=lab.country,
        region=lab.region,
        district=lab.district,
        ward=lab.ward,
        street=lab.street,
        postcode=lab.postcode,
        address_line=lab.address_line,
    )
    return {
        "id": str(lab.id),
        "name": lab.name,
        "code": lab.code,
        "description": lab.description,
        "address_line": lab.address_line,
        "country_label": lab.country.name if lab.country_id else "",
        "region_label": lab.region.name if lab.region_id else "",
        "district_label": lab.district.name if lab.district_id else "",
        "ward_label": lab.ward.name if lab.ward_id else "",
        "street_label": lab.street.name if lab.street_id else "",
        "address_breadcrumb": address_breadcrumb,
        "address_badges": [_badge(part, "neutral") for part in address_breadcrumb.split(" / ") if part],
        "country_id": str(lab.country_id) if lab.country_id else None,
        "region_id": str(lab.region_id) if lab.region_id else None,
        "district_id": str(lab.district_id) if lab.district_id else None,
        "ward_id": str(lab.ward_id) if lab.ward_id else None,
        "street_id": str(lab.street_id) if lab.street_id else None,
        "postcode": lab.postcode,
        "is_active": lab.is_active,
    }


def _study_to_dict(study: Study) -> dict[str, object]:
    return {
        "id": str(study.id),
        "name": study.name,
        "code": study.code,
        "description": study.description,
        "sponsor": study.sponsor,
        "lead_lab_id": str(study.lead_lab_id) if study.lead_lab_id else None,
        "lead_lab_name": study.lead_lab.name if study.lead_lab_id else "",
        "lead_lab_badge": _badge(study.lead_lab.name, "neutral") if study.lead_lab_id else None,
        "status": study.status,
        "status_badge": _badge(study.get_status_display(), "info"),
    }


def _site_to_dict(site: Site) -> dict[str, object]:
    studies = sorted(site.studies.all(), key=lambda item: item.name)
    primary_study_id = str(site.study_id) if site.study_id else (str(studies[0].id) if studies else None)
    address_breadcrumb = _address_breadcrumb(
        country=site.country,
        region=site.region,
        district=site.district,
        ward=site.ward,
        street=site.street,
        postcode=site.postcode,
        address_line=site.address_line,
    )
    return {
        "id": str(site.id),
        "name": site.name,
        "code": site.code,
        "description": site.description,
        "study_id": primary_study_id,
        "study_ids": [str(item.id) for item in studies],
        "study_labels": [item.name for item in studies],
        "study_badges": [_badge(item.name, "info") for item in studies],
        "lab_id": str(site.lab_id) if site.lab_id else None,
        "lab_name": site.lab.name if site.lab_id else "",
        "address_line": site.address_line,
        "country_label": site.country.name if site.country_id else "",
        "region_label": site.region.name if site.region_id else "",
        "district_label": site.district.name if site.district_id else "",
        "ward_label": site.ward.name if site.ward_id else "",
        "street_label": site.street.name if site.street_id else "",
        "address_breadcrumb": address_breadcrumb,
        "address_badges": [_badge(part, "neutral") for part in address_breadcrumb.split(" / ") if part],
        "country_id": str(site.country_id) if site.country_id else None,
        "region_id": str(site.region_id) if site.region_id else None,
        "district_id": str(site.district_id) if site.district_id else None,
        "ward_id": str(site.ward_id) if site.ward_id else None,
        "street_id": str(site.street_id) if site.street_id else None,
        "postcode": site.postcode,
        "is_active": site.is_active,
    }


def _parse_decimal(value, *, field: str, default: str | None = None):
    raw = value if value is not None else default
    if raw is None:
        return None, JsonResponse({"error": f"{field} is required"}, status=400)
    try:
        return Decimal(str(raw)), None
    except (InvalidOperation, TypeError, ValueError):
        return None, JsonResponse({"error": f"invalid_{field}"}, status=400)


def _parse_optional_received_at(value):
    if value in (None, ""):
        return None, None
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(f"{raw}T00:00:00" if len(raw) == 10 else raw)
    except ValueError:
        return None, JsonResponse({"error": "invalid_received_at"}, status=400)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed, None


def _biospecimen_type_to_dict(item: BiospecimenType) -> dict[str, object]:
    return {
        "id": str(item.id),
        "name": item.name,
        "key": item.key,
        "description": item.description,
        "identifier_prefix": item.identifier_prefix,
        "barcode_prefix": item.barcode_prefix,
        "sequence_padding": item.sequence_padding,
        "next_sequence": item.next_sequence,
        "is_active": item.is_active,
    }


def _biospecimen_to_dict(item: Biospecimen) -> dict[str, object]:
    return {
        "id": str(item.id),
        "sample_type_id": str(item.sample_type_id),
        "sample_identifier": item.sample_identifier,
        "barcode": item.barcode,
        "kind": item.kind,
        "status": item.status,
        "subject_identifier": item.subject_identifier,
        "external_identifier": item.external_identifier,
        "study_id": str(item.study_id) if item.study_id else None,
        "site_id": str(item.site_id) if item.site_id else None,
        "lab_id": str(item.lab_id) if item.lab_id else None,
        "parent_specimen_id": str(item.parent_specimen_id) if item.parent_specimen_id else None,
        "lineage_root_id": str(item.lineage_root_id) if item.lineage_root_id else None,
        "quantity": str(item.quantity),
        "quantity_unit": item.quantity_unit,
        "metadata": item.metadata,
        "collected_at": item.collected_at.isoformat() if item.collected_at else None,
        "received_at": item.received_at.isoformat() if item.received_at else None,
        "aliquot_ids": [str(child.id) for child in item.aliquots.all()],
        "pool_ids": [str(member.pool_id) for member in item.pool_memberships.all()],
        "is_active": item.is_active,
    }


def _biospecimen_pool_to_dict(item: BiospecimenPool) -> dict[str, object]:
    return {
        "id": str(item.id),
        "sample_type_id": str(item.sample_type_id),
        "pool_identifier": item.pool_identifier,
        "barcode": item.barcode,
        "status": item.status,
        "study_id": str(item.study_id) if item.study_id else None,
        "site_id": str(item.site_id) if item.site_id else None,
        "lab_id": str(item.lab_id) if item.lab_id else None,
        "quantity": str(item.quantity),
        "quantity_unit": item.quantity_unit,
        "metadata": item.metadata,
        "member_ids": [str(member.specimen_id) for member in item.members.all()],
        "is_active": item.is_active,
    }


def _manifest_item_to_dict(item: AccessioningManifestItem) -> dict[str, object]:
    return {
        "id": str(item.id),
        "manifest_id": str(item.manifest_id),
        "biospecimen_id": str(item.biospecimen_id) if item.biospecimen_id else None,
        "position": item.position,
        "expected_subject_identifier": item.expected_subject_identifier,
        "expected_sample_identifier": item.expected_sample_identifier,
        "expected_barcode": item.expected_barcode,
        "quantity": str(item.quantity),
        "quantity_unit": item.quantity_unit,
        "collection_status": item.collection_status,
        "notes": item.notes,
        "metadata": item.metadata,
        "status": item.status,
        "received_at": item.received_at.isoformat() if item.received_at else None,
    }


def _accessioning_manifest_to_dict(item: AccessioningManifest) -> dict[str, object]:
    return {
        "id": str(item.id),
        "manifest_identifier": item.manifest_identifier,
        "sample_type_id": str(item.sample_type_id),
        "study_id": str(item.study_id) if item.study_id else None,
        "site_id": str(item.site_id) if item.site_id else None,
        "lab_id": str(item.lab_id) if item.lab_id else None,
        "status": item.status,
        "source_system": item.source_system,
        "source_reference": item.source_reference,
        "notes": item.notes,
        "metadata": item.metadata,
        "created_by": item.created_by,
        "received_at": item.received_at.isoformat() if item.received_at else None,
        "item_count": item.items.count(),
    }


def _receiving_event_to_dict(item: ReceivingEvent) -> dict[str, object]:
    return {
        "id": str(item.id),
        "manifest_id": str(item.manifest_id) if item.manifest_id else None,
        "manifest_item_id": str(item.manifest_item_id) if item.manifest_item_id else None,
        "biospecimen_id": str(item.biospecimen_id),
        "kind": item.kind,
        "received_by": item.received_by,
        "scan_value": item.scan_value,
        "notes": item.notes,
        "metadata": item.metadata,
        "received_at": item.received_at.isoformat(),
    }


def _receiving_discrepancy_to_dict(item: ReceivingDiscrepancy) -> dict[str, object]:
    return {
        "id": str(item.id),
        "manifest_id": str(item.manifest_id) if item.manifest_id else None,
        "manifest_item_id": str(item.manifest_item_id) if item.manifest_item_id else None,
        "biospecimen_id": str(item.biospecimen_id) if item.biospecimen_id else None,
        "code": item.code,
        "status": item.status,
        "notes": item.notes,
        "expected_data": item.expected_data,
        "actual_data": item.actual_data,
        "recorded_by": item.recorded_by,
    }


def _plate_layout_to_dict(item: PlateLayoutTemplate) -> dict[str, object]:
    return {
        "id": str(item.id),
        "name": item.name,
        "key": item.key,
        "description": item.description,
        "rows": item.rows,
        "columns": item.columns,
        "capacity": item.rows * item.columns,
        "is_active": item.is_active,
    }


def _batch_plate_assignment_to_dict(item) -> dict[str, object]:
    return {
        "id": str(item.id),
        "biospecimen_id": str(item.biospecimen_id),
        "sample_identifier": item.biospecimen.sample_identifier,
        "barcode": item.biospecimen.barcode,
        "subject_identifier": item.biospecimen.subject_identifier,
        "position_index": item.position_index,
        "well_label": item.well_label,
        "metadata": item.metadata,
    }


def _batch_plate_to_dict(item) -> dict[str, object]:
    return {
        "id": str(item.id),
        "batch_id": str(item.batch_id),
        "layout_template": _plate_layout_to_dict(item.layout_template),
        "plate_identifier": item.plate_identifier,
        "sequence_number": item.sequence_number,
        "label": item.label,
        "metadata": item.metadata,
        "is_active": item.is_active,
        "assignments": [
            _batch_plate_assignment_to_dict(assignment)
            for assignment in item.assignments.select_related("biospecimen").order_by("position_index")
        ],
    }


def _processing_batch_to_dict(item: ProcessingBatch, *, include_plates: bool = False) -> dict[str, object]:
    payload = {
        "id": str(item.id),
        "batch_identifier": item.batch_identifier,
        "sample_type_id": str(item.sample_type_id),
        "study_id": str(item.study_id) if item.study_id else None,
        "site_id": str(item.site_id) if item.site_id else None,
        "lab_id": str(item.lab_id) if item.lab_id else None,
        "status": item.status,
        "notes": item.notes,
        "metadata": item.metadata,
        "created_by": item.created_by,
        "plate_count": item.plates.count(),
        "assigned_specimen_count": sum(plate.assignments.count() for plate in item.plates.all()),
    }
    if include_plates:
        payload["plates"] = [
            _batch_plate_to_dict(plate)
            for plate in item.plates.select_related("layout_template").order_by("sequence_number")
        ]
    return payload


def _print_job_summary_to_dict(item) -> dict[str, object]:
    return {
        "id": str(item.id),
        "template_ref": item.template_ref,
        "output_format": item.output_format,
        "destination": item.destination,
        "status": item.status,
        "gateway_metadata": item.gateway_metadata,
    }


def _vocabulary_item_to_dict(item: MetadataVocabularyItem) -> dict[str, object]:
    return {
        "id": str(item.id),
        "value": item.value,
        "label": item.label,
        "sort_order": item.sort_order,
        "is_active": item.is_active,
    }


def _vocabulary_domain_to_dict(domain: MetadataVocabularyDomain) -> dict[str, object]:
    vocabulary_count = len(getattr(domain, "_prefetched_objects_cache", {}).get("vocabularies", []))
    if not vocabulary_count:
        vocabulary_count = domain.vocabularies.count()
    return {
        "id": str(domain.id),
        "name": domain.name,
        "code": domain.code,
        "description": domain.description,
        "is_active": domain.is_active,
        "vocabulary_count": vocabulary_count,
    }


def _vocabulary_to_dict(vocabulary: MetadataVocabulary) -> dict[str, object]:
    return {
        "id": str(vocabulary.id),
        "name": vocabulary.name,
        "code": vocabulary.code,
        "description": vocabulary.description,
        "domain_id": str(vocabulary.domain_id),
        "domain_code": vocabulary.domain.code,
        "domain_name": vocabulary.domain.name,
        "is_active": vocabulary.is_active,
        "items": [_vocabulary_item_to_dict(item) for item in vocabulary.items.order_by("sort_order", "label")],
    }


def _field_definition_to_dict(field: MetadataFieldDefinition) -> dict[str, object]:
    vocabulary_items = []
    if field.vocabulary_id:
        vocabulary_items = [
            {"label": item.label, "value": item.value}
            for item in field.vocabulary.items.filter(is_active=True).order_by("sort_order", "label")
        ]
    return {
        "id": str(field.id),
        "name": field.name,
        "code": field.code,
        "description": field.description,
        "field_type": field.field_type,
        "help_text": field.help_text,
        "placeholder": field.placeholder,
        "vocabulary_id": str(field.vocabulary_id) if field.vocabulary_id else None,
        "vocabulary_items": vocabulary_items,
        "default_value": field.default_value,
        "config": field.config,
        "is_active": field.is_active,
    }


def _formbuilder_type_from_field_type(field_type: str) -> str:
    return {
        MetadataFieldDefinition.FieldType.TEXT: "text",
        MetadataFieldDefinition.FieldType.LONG_TEXT: "textarea",
        MetadataFieldDefinition.FieldType.INTEGER: "number",
        MetadataFieldDefinition.FieldType.DECIMAL: "number",
        MetadataFieldDefinition.FieldType.BOOLEAN: "checkbox",
        MetadataFieldDefinition.FieldType.DATE: "date",
        MetadataFieldDefinition.FieldType.DATETIME: "text",
        MetadataFieldDefinition.FieldType.CHOICE: "select",
        MetadataFieldDefinition.FieldType.MULTI_CHOICE: "checkbox-group",
    }[field_type]


def _schema_field_to_dict(field: MetadataSchemaField) -> dict[str, object]:
    vocabulary_items = []
    if field.vocabulary_id:
        vocabulary_items = [
            {"label": item.label, "value": item.value}
            for item in field.vocabulary.items.filter(is_active=True).order_by("sort_order", "label")
        ]
    formbuilder_type = _formbuilder_type_from_field_type(field.field_type)
    return {
        "id": str(field.id),
        "field_definition_id": str(field.field_definition_id) if field.field_definition_id else None,
        "field_definition_code": field.field_key,
        "field_definition_name": field.name,
        "field_type": field.field_type,
        "field_key": field.field_key,
        "name": field.name,
        "description": field.description,
        "position": field.position,
        "required": field.required,
        "validation_rules": dict(field.validation_rules or {}),
        "condition": dict(field.condition or {}),
        "help_text": field.help_text,
        "placeholder": field.placeholder,
        "vocabulary_id": str(field.vocabulary_id) if field.vocabulary_id else None,
        "default_value": field.default_value,
        "config": dict(field.config or {}),
        "vocabulary_items": vocabulary_items,
        "formbuilder": {
            "name": field.field_key,
            "label": field.name,
            "type": formbuilder_type,
            "subtype": (
                "textarea"
                if field.field_type == MetadataFieldDefinition.FieldType.LONG_TEXT
                else (
                    "integer"
                    if field.field_type == MetadataFieldDefinition.FieldType.INTEGER
                    else (
                        "datetime-local"
                        if field.field_type == MetadataFieldDefinition.FieldType.DATETIME
                        else "text"
                    )
                )
            ),
            "required": field.required,
            "placeholder": field.placeholder,
            "description": field.help_text,
            "multiple": field.field_type == MetadataFieldDefinition.FieldType.MULTI_CHOICE,
            "values": vocabulary_items,
            "value": field.default_value,
            "ui_step": str(field.config.get("ui_step") or "metadata"),
        },
    }


def _schema_version_to_dict(version: MetadataSchemaVersion) -> dict[str, object]:
    return {
        "id": str(version.id),
        "schema_id": str(version.schema_id),
        "schema_name": version.schema.name,
        "schema_code": version.schema.code,
        "version_number": version.version_number,
        "status": version.status,
        "is_editable": version.status == MetadataSchemaVersion.Status.DRAFT,
        "change_summary": version.change_summary,
        "fields": [_schema_field_to_dict(item) for item in version.fields.select_related("vocabulary").order_by("position", "field_key")],
    }


def _schema_to_dict(schema: MetadataSchema) -> dict[str, object]:
    versions = [_schema_version_to_dict(item) for item in schema.versions.order_by("-version_number")]
    draft_version = next((item for item in versions if item["status"] == MetadataSchemaVersion.Status.DRAFT), None)
    published_version = next((item for item in versions if item["status"] == MetadataSchemaVersion.Status.PUBLISHED), None)
    return {
        "id": str(schema.id),
        "name": schema.name,
        "code": schema.code,
        "description": schema.description,
        "purpose": schema.purpose,
        "is_active": schema.is_active,
        "draft_version_id": draft_version["id"] if draft_version else None,
        "published_version_id": published_version["id"] if published_version else None,
        "versions": versions,
    }


def _schema_binding_to_dict(binding: MetadataSchemaBinding) -> dict[str, object]:
    return {
        "id": str(binding.id),
        "schema_version_id": str(binding.schema_version_id),
        "schema_id": str(binding.schema_version.schema_id),
        "schema_code": binding.schema_version.schema.code,
        "version_number": binding.schema_version.version_number,
        "target_type": binding.target_type,
        "target_key": binding.target_key,
        "target_label": binding.target_label,
        "is_active": binding.is_active,
    }


def _resolve_optional_fk(model, raw_id, error_code: str):
    if not raw_id:
        return None, None
    try:
        return model.objects.get(id=raw_id), None
    except (ValidationError, model.DoesNotExist):
        return None, JsonResponse({"error": error_code}, status=404)


def _resolve_optional_fk_list(model, raw_ids, error_code: str):
    if raw_ids in (None, ""):
        return [], None
    if not isinstance(raw_ids, list):
        return None, JsonResponse({"error": f"{error_code}_invalid"}, status=400)
    resolved = []
    seen = set()
    for raw_id in raw_ids:
        if not raw_id:
            continue
        obj, error = _resolve_optional_fk(model, raw_id, error_code)
        if error:
            return None, error
        key = str(obj.id)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(obj)
    return resolved, None


def _normalize_code(name: str, raw_code: object) -> str:
    return slugify(str(raw_code or "").strip() or name)


def _parse_positive_int_query(request, key: str, *, default: int, maximum: int) -> int | JsonResponse:
    raw_value = str(request.GET.get(key) or "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return JsonResponse({"error": f"invalid_{key}"}, status=400)
    if value < 0:
        return JsonResponse({"error": f"invalid_{key}"}, status=400)
    return min(value, maximum)


def _expand_address_hierarchy(*, country, region, district, ward, street):
    resolved_country = country
    resolved_region = region
    resolved_district = district
    resolved_ward = ward
    resolved_street = street

    if resolved_street:
        if resolved_ward and resolved_street.ward_id != resolved_ward.id:
            return None, JsonResponse({"error": "street_ward_mismatch"}, status=400)
        resolved_ward = resolved_street.ward
    if resolved_ward:
        if resolved_district and resolved_ward.district_id != resolved_district.id:
            return None, JsonResponse({"error": "ward_district_mismatch"}, status=400)
        resolved_district = resolved_ward.district
    if resolved_district:
        if resolved_region and resolved_district.region_id != resolved_region.id:
            return None, JsonResponse({"error": "district_region_mismatch"}, status=400)
        resolved_region = resolved_district.region
    if resolved_region:
        if resolved_country and resolved_region.country_id != resolved_country.id:
            return None, JsonResponse({"error": "region_country_mismatch"}, status=400)
        resolved_country = resolved_region.country
    return {
        "country": resolved_country,
        "region": resolved_region,
        "district": resolved_district,
        "ward": resolved_ward,
        "street": resolved_street,
    }, None


def _resolve_postcode_from_payload(raw_postcode_id, raw_postcode_code, street: Street | None):
    if raw_postcode_id:
        postcode, error = _resolve_optional_fk(Postcode, raw_postcode_id, "postcode_not_found")
        if error:
            return None, error
        return (postcode.code if postcode else ""), None
    postcode_code = str(raw_postcode_code or "").strip()
    if not postcode_code and street:
        matches = list(Postcode.objects.filter(street=street).order_by("code")[:2])
        if len(matches) == 1:
            return matches[0].code, None
    if not postcode_code:
        return "", None
    queryset = Postcode.objects.filter(code=postcode_code)
    if street:
        queryset = queryset.filter(street=street)
    matches = list(queryset[:2])
    if not matches:
        return postcode_code, None
    if len(matches) > 1:
        return None, JsonResponse({"error": "postcode_ambiguous"}, status=400)
    return matches[0].code, None


def _build_lab_from_payload(lab: Lab, payload: dict[str, object]):
    country, error = _resolve_optional_fk(Country, payload.get("country_id"), "country_not_found")
    if error:
        return error
    region, error = _resolve_optional_fk(Region, payload.get("region_id"), "region_not_found")
    if error:
        return error
    district, error = _resolve_optional_fk(District, payload.get("district_id"), "district_not_found")
    if error:
        return error
    ward, error = _resolve_optional_fk(Ward, payload.get("ward_id"), "ward_not_found")
    if error:
        return error
    street, error = _resolve_optional_fk(Street, payload.get("street_id"), "street_not_found")
    if error:
        return error
    hierarchy, error = _expand_address_hierarchy(
        country=country,
        region=region,
        district=district,
        ward=ward,
        street=street,
    )
    if error:
        return error
    postcode, error = _resolve_postcode_from_payload(payload.get("postcode_id"), payload.get("postcode"), street)
    if error:
        return error

    name = str(payload.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)
    code = _normalize_code(name, payload.get("code"))
    if not code:
        return JsonResponse({"error": "code is required"}, status=400)

    lab.name = name
    lab.code = code
    lab.description = str(payload.get("description") or "").strip()
    lab.address_line = str(payload.get("address_line") or "").strip()
    lab.country = hierarchy["country"]
    lab.region = hierarchy["region"]
    lab.district = hierarchy["district"]
    lab.ward = hierarchy["ward"]
    lab.street = hierarchy["street"]
    lab.postcode = postcode
    lab.is_active = bool(payload.get("is_active", True))
    return None


def _build_study_from_payload(study: Study, payload: dict[str, object]):
    lead_lab, error = _resolve_optional_fk(Lab, payload.get("lead_lab_id"), "lab_not_found")
    if error:
        return error
    name = str(payload.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)
    code = _normalize_code(name, payload.get("code"))
    if not code:
        return JsonResponse({"error": "code is required"}, status=400)
    study.name = name
    study.code = code
    study.description = str(payload.get("description") or "").strip()
    study.sponsor = str(payload.get("sponsor") or "").strip()
    study.lead_lab = lead_lab
    status = str(payload.get("status") or Study.Status.ACTIVE)
    if status not in Study.Status.values:
        return JsonResponse({"error": "invalid_status"}, status=400)
    study.status = status
    return None


def _build_site_from_payload(site: Site, payload: dict[str, object]):
    studies, error = _resolve_optional_fk_list(Study, payload.get("study_ids"), "study_not_found")
    if error:
        return error
    study, error = _resolve_optional_fk(Study, payload.get("study_id"), "study_not_found")
    if error:
        return error
    if study and all(str(item.id) != str(study.id) for item in studies):
        studies = [study, *studies]
    lab, error = _resolve_optional_fk(Lab, payload.get("lab_id"), "lab_not_found")
    if error:
        return error
    country, error = _resolve_optional_fk(Country, payload.get("country_id"), "country_not_found")
    if error:
        return error
    region, error = _resolve_optional_fk(Region, payload.get("region_id"), "region_not_found")
    if error:
        return error
    district, error = _resolve_optional_fk(District, payload.get("district_id"), "district_not_found")
    if error:
        return error
    ward, error = _resolve_optional_fk(Ward, payload.get("ward_id"), "ward_not_found")
    if error:
        return error
    street, error = _resolve_optional_fk(Street, payload.get("street_id"), "street_not_found")
    if error:
        return error
    hierarchy, error = _expand_address_hierarchy(
        country=country,
        region=region,
        district=district,
        ward=ward,
        street=street,
    )
    if error:
        return error
    postcode, error = _resolve_postcode_from_payload(payload.get("postcode_id"), payload.get("postcode"), street)
    if error:
        return error
    name = str(payload.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)
    code = _normalize_code(name, payload.get("code"))
    if not code:
        return JsonResponse({"error": "code is required"}, status=400)
    site.name = name
    site.code = code
    site.description = str(payload.get("description") or "").strip()
    site.study = studies[0] if studies else study
    site.lab = lab
    site.address_line = str(payload.get("address_line") or "").strip()
    site.country = hierarchy["country"]
    site.region = hierarchy["region"]
    site.district = hierarchy["district"]
    site.ward = hierarchy["ward"]
    site.street = hierarchy["street"]
    site.postcode = postcode
    site.is_active = bool(payload.get("is_active", True))
    site._pending_studies = studies
    return None


def _save_model(instance):
    try:
        instance.full_clean()
        instance.save()
    except ValidationError:
        return JsonResponse({"error": "validation_error"}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "conflict"}, status=409)
    return None


def _save_site_model(site: Site):
    error = _save_model(site)
    if error:
        return error
    pending_studies = getattr(site, "_pending_studies", None)
    if pending_studies is not None:
        site.studies.set(pending_studies)
        delattr(site, "_pending_studies")
    return None


def _build_vocabulary_from_payload(vocabulary: MetadataVocabulary, payload: dict[str, object]):
    if not payload.get("name"):
        return JsonResponse({"error": "name is required"}, status=400)
    if not payload.get("code"):
        return JsonResponse({"error": "code is required"}, status=400)
    domain = None
    raw_domain_id = payload.get("domain_id")
    raw_domain_code = str(payload.get("domain_code") or "").strip()
    if raw_domain_id:
        domain, error = _resolve_optional_fk(MetadataVocabularyDomain, raw_domain_id, "domain_not_found")
        if error:
            return error
    elif raw_domain_code:
        try:
            domain = MetadataVocabularyDomain.objects.get(code=raw_domain_code)
        except MetadataVocabularyDomain.DoesNotExist:
            return JsonResponse({"error": "domain_not_found"}, status=404)
    else:
        domain = get_default_metadata_vocabulary_domain()
    vocabulary.name = str(payload.get("name")).strip()
    vocabulary.code = str(payload.get("code")).strip()
    vocabulary.description = str(payload.get("description") or "").strip()
    vocabulary.domain = domain
    vocabulary.is_active = bool(payload.get("is_active", True))
    return None


def _sync_vocabulary_items(vocabulary: MetadataVocabulary, items_payload: object):
    if items_payload is None:
        return None
    if not isinstance(items_payload, list):
        return JsonResponse({"error": "items must be a list"}, status=400)
    retained_ids: list[str] = []
    for index, item_payload in enumerate(items_payload):
        if not isinstance(item_payload, dict):
            return JsonResponse({"error": "item must be an object"}, status=400)
        value = str(item_payload.get("value") or "").strip()
        label = str(item_payload.get("label") or "").strip()
        if not value or not label:
            return JsonResponse({"error": "item value and label are required"}, status=400)
        item_id = item_payload.get("id")
        if item_id:
            try:
                item = MetadataVocabularyItem.objects.get(id=item_id, vocabulary=vocabulary)
            except (ValidationError, MetadataVocabularyItem.DoesNotExist):
                return JsonResponse({"error": "vocabulary_item_not_found"}, status=404)
        else:
            item = MetadataVocabularyItem(vocabulary=vocabulary)
        item.value = value
        item.label = label
        item.sort_order = int(item_payload.get("sort_order") or index)
        item.is_active = bool(item_payload.get("is_active", True))
        error = _save_model(item)
        if error:
            return error
        retained_ids.append(str(item.id))
    MetadataVocabularyItem.objects.filter(vocabulary=vocabulary).exclude(id__in=retained_ids).delete()
    return None


def _build_field_definition_from_payload(field: MetadataFieldDefinition, payload: dict[str, object]):
    vocabulary, error = _resolve_optional_fk(MetadataVocabulary, payload.get("vocabulary_id"), "vocabulary_not_found")
    if error:
        return error
    if not payload.get("name"):
        return JsonResponse({"error": "name is required"}, status=400)
    if not payload.get("code"):
        return JsonResponse({"error": "code is required"}, status=400)
    field_type = str(payload.get("field_type") or "")
    if field_type not in MetadataFieldDefinition.FieldType.values:
        return JsonResponse({"error": "invalid_field_type"}, status=400)
    config = payload.get("config") or {}
    if not isinstance(config, dict):
        return JsonResponse({"error": "config must be an object"}, status=400)
    field.name = str(payload.get("name")).strip()
    field.code = str(payload.get("code")).strip()
    field.description = str(payload.get("description") or "").strip()
    field.field_type = field_type
    field.help_text = str(payload.get("help_text") or "").strip()
    field.placeholder = str(payload.get("placeholder") or "").strip()
    field.vocabulary = vocabulary
    field.default_value = payload.get("default_value")
    field.config = config
    field.is_active = bool(payload.get("is_active", True))
    return None


def _build_schema_from_payload(schema: MetadataSchema, payload: dict[str, object]):
    if not payload.get("name"):
        return JsonResponse({"error": "name is required"}, status=400)
    if not payload.get("code"):
        return JsonResponse({"error": "code is required"}, status=400)
    schema.name = str(payload.get("name")).strip()
    schema.code = str(payload.get("code")).strip()
    schema.description = str(payload.get("description") or "").strip()
    schema.purpose = str(payload.get("purpose") or "").strip()
    schema.is_active = bool(payload.get("is_active", True))
    return None


def _apply_field_definition_defaults(schema_field: MetadataSchemaField, field_definition: MetadataFieldDefinition) -> None:
    schema_field.field_definition = field_definition
    schema_field.name = field_definition.name
    schema_field.description = field_definition.description
    schema_field.field_type = field_definition.field_type
    schema_field.help_text = field_definition.help_text
    schema_field.placeholder = field_definition.placeholder
    schema_field.vocabulary = field_definition.vocabulary
    schema_field.default_value = field_definition.default_value
    schema_field.config = dict(field_definition.config or {})


def _build_schema_field_from_payload(
    schema_field: MetadataSchemaField,
    field_payload: dict[str, object],
    *,
    index: int,
) -> JsonResponse | None:
    field_definition = None
    if field_payload.get("field_definition_id"):
        field_definition, error = _resolve_optional_fk(
            MetadataFieldDefinition,
            field_payload.get("field_definition_id"),
            "field_definition_not_found",
        )
        if error:
            return error
        if field_definition:
            _apply_field_definition_defaults(schema_field, field_definition)

    name = str(field_payload.get("name") or schema_field.name or "").strip()
    field_type = str(field_payload.get("field_type") or schema_field.field_type or "").strip()
    field_key = str(field_payload.get("field_key") or slugify(name) or "").strip()
    if not name:
        return JsonResponse({"error": "field name is required"}, status=400)
    if not field_type or field_type not in MetadataFieldDefinition.FieldType.values:
        return JsonResponse({"error": "invalid_field_type"}, status=400)
    if not field_key:
        return JsonResponse({"error": "field_key is required"}, status=400)

    vocabulary, error = _resolve_optional_fk(MetadataVocabulary, field_payload.get("vocabulary_id"), "vocabulary_not_found")
    if error:
        return error
    if vocabulary is None and field_definition is not None:
        vocabulary = field_definition.vocabulary

    validation_rules = field_payload.get("validation_rules") or {}
    condition = field_payload.get("condition") or {}
    config = field_payload.get("config")
    if config is None:
        config = dict(schema_field.config or {})
    if not isinstance(validation_rules, dict):
        return JsonResponse({"error": "validation_rules must be an object"}, status=400)
    if not isinstance(condition, dict):
        return JsonResponse({"error": "condition must be an object"}, status=400)
    if not isinstance(config, dict):
        return JsonResponse({"error": "config must be an object"}, status=400)

    schema_field.name = name
    schema_field.description = str(field_payload.get("description") or schema_field.description or "").strip()
    schema_field.field_type = field_type
    schema_field.field_key = field_key
    schema_field.help_text = str(field_payload.get("help_text") or schema_field.help_text or "").strip()
    schema_field.placeholder = str(field_payload.get("placeholder") or schema_field.placeholder or "").strip()
    schema_field.vocabulary = vocabulary
    schema_field.default_value = field_payload.get("default_value", schema_field.default_value)
    schema_field.config = config
    schema_field.position = int(field_payload.get("position") or index)
    schema_field.required = bool(field_payload.get("required", False))
    schema_field.validation_rules = validation_rules
    schema_field.condition = condition
    return None


def _sync_schema_version_fields(version: MetadataSchemaVersion, fields_payload: object) -> JsonResponse | None:
    if not isinstance(fields_payload, list):
        return JsonResponse({"error": "fields must be a list"}, status=400)
    retained_ids: list[str] = []
    for index, field_payload in enumerate(fields_payload, start=1):
        if not isinstance(field_payload, dict):
            return JsonResponse({"error": "field must be an object"}, status=400)
        field_id = field_payload.get("id")
        if field_id:
            try:
                schema_field = MetadataSchemaField.objects.get(id=field_id, schema_version=version)
            except (ValidationError, MetadataSchemaField.DoesNotExist):
                return JsonResponse({"error": "schema_field_not_found"}, status=404)
        else:
            schema_field = MetadataSchemaField(schema_version=version)
        error = _build_schema_field_from_payload(schema_field, field_payload, index=index)
        if error:
            return error
        error = _save_model(schema_field)
        if error:
            return error
        retained_ids.append(str(schema_field.id))
    MetadataSchemaField.objects.filter(schema_version=version).exclude(id__in=retained_ids).delete()
    return None


def _clone_schema_version_fields(source_version: MetadataSchemaVersion, target_version: MetadataSchemaVersion) -> None:
    for field in source_version.fields.all().order_by("position", "field_key"):
        MetadataSchemaField.objects.create(
            schema_version=target_version,
            field_definition=field.field_definition,
            name=field.name,
            description=field.description,
            field_type=field.field_type,
            field_key=field.field_key,
            help_text=field.help_text,
            placeholder=field.placeholder,
            vocabulary=field.vocabulary,
            default_value=field.default_value,
            config=dict(field.config or {}),
            position=field.position,
            required=field.required,
            validation_rules=dict(field.validation_rules or {}),
            condition=dict(field.condition or {}),
        )


@csrf_exempt
def lims_dashboard_summary(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.dashboard.view')
    if forbidden:
        return forbidden
    return JsonResponse(_dashboard_payload(request))


@csrf_exempt
def lims_dashboard_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.dashboard.view')
    if forbidden:
        return forbidden
    return render(request, 'lims/dashboard.html', _page_context(request, active_nav='lims-dashboard', payload=_dashboard_payload(request)))


@csrf_exempt
def lims_reference_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.reference.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/reference.html',
        _page_context(request, active_nav='lims-reference', payload=_reference_launchpad_payload(request)),
    )


@csrf_exempt
def lims_reference_create_lab_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.reference.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/reference_create_lab.html',
        _page_context(request, active_nav='lims-reference', payload=_reference_create_lab_page_payload(request)),
    )


@csrf_exempt
def lims_reference_create_study_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.reference.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/reference_create_study.html',
        _page_context(request, active_nav='lims-reference', payload=_reference_create_study_page_payload(request)),
    )


@csrf_exempt
def lims_reference_create_site_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.reference.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/reference_create_site.html',
        _page_context(request, active_nav='lims-reference', payload=_reference_create_site_page_payload(request)),
    )


@csrf_exempt
def lims_reference_address_sync_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.reference.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/reference_address_sync.html',
        _page_context(request, active_nav='lims-reference', payload=_reference_address_sync_page_payload(request)),
    )


@csrf_exempt
def lims_metadata_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.metadata.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/metadata.html',
        _page_context(request, active_nav='lims-metadata', payload=_metadata_launchpad_payload(request)),
    )


@csrf_exempt
def lims_metadata_create_vocabulary_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.metadata.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/metadata_create_vocabulary.html',
        _page_context(request, active_nav='lims-metadata', payload=_metadata_create_vocabulary_page_payload(request)),
    )


@csrf_exempt
def lims_metadata_create_field_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.metadata.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/metadata_create_field.html',
        _page_context(request, active_nav='lims-metadata', payload=_metadata_create_field_page_payload(request)),
    )


@csrf_exempt
def lims_metadata_create_schema_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.metadata.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/metadata_create_schema.html',
        _page_context(request, active_nav='lims-metadata', payload=_metadata_create_schema_page_payload(request)),
    )


@csrf_exempt
def lims_metadata_create_binding_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.metadata.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/metadata_create_binding.html',
        _page_context(request, active_nav='lims-metadata', payload=_metadata_create_binding_page_payload(request)),
    )


@csrf_exempt
def lims_metadata_publish_version_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.metadata.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/metadata_publish_version.html',
        _page_context(request, active_nav='lims-metadata', payload=_metadata_publish_version_page_payload(request)),
    )


@csrf_exempt
def lims_biospecimens_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.artifact.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/biospecimens.html',
        _page_context(request, active_nav='lims-biospecimens', payload=_biospecimens_page_payload(request)),
    )


@csrf_exempt
def lims_receiving_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.artifact.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/receiving.html',
        _page_context(request, active_nav='lims-receiving', payload=_receiving_launchpad_payload(request)),
    )


@csrf_exempt
def lims_receiving_single_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.artifact.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/receiving_single.html',
        _page_context(request, active_nav='lims-receiving', payload=_receiving_single_page_payload(request)),
    )


@csrf_exempt
def lims_receiving_batch_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.artifact.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/receiving_batch.html',
        _page_context(request, active_nav='lims-receiving', payload=_receiving_batch_page_payload(request)),
    )


@csrf_exempt
def lims_receiving_edc_import_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.artifact.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/receiving_edc_import.html',
        _page_context(request, active_nav='lims-receiving', payload=_receiving_edc_import_page_payload(request)),
    )


@csrf_exempt
def lims_processing_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.artifact.view')
    if forbidden:
        return forbidden
    return render(
        request,
        'lims/processing.html',
        _page_context(request, active_nav='lims-processing', payload=_processing_page_payload(request)),
    )


@csrf_exempt
def lims_permissions_summary(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_lims_permission(request, 'lims.dashboard.view')
    if forbidden:
        return forbidden
    return JsonResponse(permission_summary_for_roles(request_roles(request)))


@csrf_exempt
def lims_reference_labs(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.reference.view")
        if forbidden:
            return forbidden
        items = [
            _lab_to_dict(item)
            for item in Lab.objects.select_related("country", "region", "district", "ward", "street").order_by("name")
        ]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.reference.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        lab = Lab()
        error = _build_lab_from_payload(lab, payload)
        if error:
            return error
        error = _save_model(lab)
        if error:
            return error
        return JsonResponse(_lab_to_dict(lab), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_reference_lab_detail(request, lab_id: str):
    try:
        lab = Lab.objects.get(id=lab_id)
    except (ValidationError, Lab.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.reference.view")
        if forbidden:
            return forbidden
        return JsonResponse(_lab_to_dict(lab))
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.reference.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        error = _build_lab_from_payload(lab, payload)
        if error:
            return error
        error = _save_model(lab)
        if error:
            return error
        return JsonResponse(_lab_to_dict(lab))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_reference_studies(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.reference.view")
        if forbidden:
            return forbidden
        items = [_study_to_dict(item) for item in Study.objects.select_related("lead_lab").order_by("name")]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.reference.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        study = Study()
        error = _build_study_from_payload(study, payload)
        if error:
            return error
        error = _save_model(study)
        if error:
            return error
        return JsonResponse(_study_to_dict(study), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_reference_study_detail(request, study_id: str):
    try:
        study = Study.objects.get(id=study_id)
    except (ValidationError, Study.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.reference.view")
        if forbidden:
            return forbidden
        return JsonResponse(_study_to_dict(study))
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.reference.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        error = _build_study_from_payload(study, payload)
        if error:
            return error
        error = _save_model(study)
        if error:
            return error
        return JsonResponse(_study_to_dict(study))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_reference_sites(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.reference.view")
        if forbidden:
            return forbidden
        items = [
            _site_to_dict(item)
            for item in Site.objects.select_related("study", "lab", "country", "region", "district", "ward", "street")
            .prefetch_related("studies")
            .order_by("name")
        ]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.reference.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        site = Site()
        error = _build_site_from_payload(site, payload)
        if error:
            return error
        error = _save_site_model(site)
        if error:
            return error
        return JsonResponse(_site_to_dict(site), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_reference_site_detail(request, site_id: str):
    try:
        site = Site.objects.prefetch_related("studies").get(id=site_id)
    except (ValidationError, Site.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.reference.view")
        if forbidden:
            return forbidden
        return JsonResponse(_site_to_dict(site))
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.reference.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        error = _build_site_from_payload(site, payload)
        if error:
            return error
        error = _save_site_model(site)
        if error:
            return error
        return JsonResponse(_site_to_dict(site))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_reference_select_options(request):
    if request.method != "GET":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.reference.view")
    if forbidden:
        return forbidden

    source = (request.GET.get("source") or "").strip()
    query = (request.GET.get("q") or "").strip().lower()
    try:
        limit = max(1, min(int(request.GET.get("limit", "50")), 50))
    except ValueError:
        return JsonResponse({"error": "invalid_limit"}, status=400)
    items = []
    if source == "labs":
        queryset = Lab.objects.order_by("name")
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(code__icontains=query))
        items = [_option(str(item.id), item.name, item.code) for item in queryset[:limit]]
    elif source == "studies":
        queryset = Study.objects.order_by("name")
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(code__icontains=query))
        items = [_option(str(item.id), item.name, item.code) for item in queryset[:limit]]
    elif source == "sites":
        queryset = Site.objects.order_by("name")
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(code__icontains=query))
        items = [_option(str(item.id), item.name, item.code) for item in queryset[:limit]]
    elif source == "countries":
        queryset = Country.objects.order_by("name")
        if query:
            queryset = queryset.filter(name__icontains=query)
        items = [_option(str(item.id), item.name, item.code) for item in queryset[:limit]]
    elif source == "regions":
        queryset = Region.objects.select_related("country").order_by("name")
        if request.GET.get("country_id"):
            queryset = queryset.filter(country_id=request.GET["country_id"])
        if query:
            queryset = queryset.filter(name__icontains=query)
        items = [_option(str(item.id), item.name, item.country.name) for item in queryset[:limit]]
    elif source == "districts":
        queryset = District.objects.select_related("region", "region__country").order_by("name")
        if request.GET.get("region_id"):
            queryset = queryset.filter(region_id=request.GET["region_id"])
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(region__name__icontains=query))
        items = [_option(str(item.id), item.name, item.region.name) for item in queryset[:limit]]
    elif source == "wards":
        queryset = Ward.objects.select_related("district", "district__region").order_by("name")
        if request.GET.get("district_id"):
            queryset = queryset.filter(district_id=request.GET["district_id"])
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(district__name__icontains=query))
        items = [
            _option(str(item.id), item.name, f"{item.district.name} / {item.district.region.name}")
            for item in queryset[:limit]
        ]
    elif source == "streets":
        queryset = Street.objects.select_related("ward", "ward__district", "ward__district__region").order_by("name")
        if request.GET.get("ward_id"):
            queryset = queryset.filter(ward_id=request.GET["ward_id"])
        if request.GET.get("district_id"):
            queryset = queryset.filter(ward__district_id=request.GET["district_id"])
        if request.GET.get("region_id"):
            queryset = queryset.filter(ward__district__region_id=request.GET["region_id"])
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(ward__name__icontains=query)
                | Q(ward__district__name__icontains=query)
                | Q(ward__district__region__name__icontains=query)
            )
        items = [
            _option(str(item.id), item.name, f"{item.ward.name} / {item.ward.district.name} / {item.ward.district.region.name}")
            for item in queryset[:limit]
        ]
    elif source == "postcodes":
        queryset = Postcode.objects.select_related("street", "street__ward", "street__ward__district").order_by("code")
        if request.GET.get("street_id"):
            queryset = queryset.filter(street_id=request.GET["street_id"])
        if query:
            queryset = queryset.filter(code__icontains=query)
        items = [_option(str(item.id), item.code, item.street.name) for item in queryset[:limit]]
    else:
        return JsonResponse({"error": "unsupported_source"}, status=400)
    return JsonResponse({"source": source, "items": items, "results": items})


@csrf_exempt
def lims_reference_address_sync_runs(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.reference.view")
        if forbidden:
            return forbidden
        items = [sync_run_to_dict(item) for item in TanzaniaAddressSyncRun.objects.order_by("-created_at")]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.reference.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        mode = str(payload.get("mode") or TanzaniaAddressSyncRun.Mode.INCREMENTAL)
        if mode not in TanzaniaAddressSyncRun.Mode.values:
            return JsonResponse({"error": "invalid_mode"}, status=400)
        request_budget = int(payload.get("request_budget") or 10)
        throttle_seconds = int(payload.get("throttle_seconds") or 2)
        if request_budget < 1 or request_budget > 25:
            return JsonResponse({"error": "request_budget must be between 1 and 25"}, status=400)
        if throttle_seconds < 1 or throttle_seconds > 30:
            return JsonResponse({"error": "throttle_seconds must be between 1 and 30"}, status=400)
        run = TanzaniaAddressSyncRun.objects.create(
            mode=mode,
            request_budget=request_budget,
            throttle_seconds=throttle_seconds,
            triggered_by=getattr(request, "auth_user_id", None) or request.headers.get("X-User-Id", ""),
        )
        sync_tanzania_address_run.delay(
            tenant_schema=getattr(getattr(request, "tenant", None), "schema_name", "public"),
            run_id=str(run.id),
        )
        return JsonResponse(sync_run_to_dict(run), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_vocabulary_domains(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        search_term = str(request.GET.get("search") or request.GET.get("q") or "").strip()
        queryset = MetadataVocabularyDomain.objects.prefetch_related("vocabularies").order_by("name")
        if search_term:
            queryset = queryset.filter(
                Q(name__icontains=search_term)
                | Q(code__icontains=search_term)
                | Q(description__icontains=search_term)
            )
        return JsonResponse({"items": [_vocabulary_domain_to_dict(item) for item in queryset]})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        name = str(payload.get("name") or "").strip()
        if not name:
            return JsonResponse({"error": "name is required"}, status=400)
        code = _normalize_code(name, payload.get("code"))
        if not code:
            return JsonResponse({"error": "code is required"}, status=400)
        domain = MetadataVocabularyDomain(
            name=name,
            code=code,
            description=str(payload.get("description") or "").strip(),
            is_active=bool(payload.get("is_active", True)),
        )
        error = _save_model(domain)
        if error:
            return error
        return JsonResponse(_vocabulary_domain_to_dict(domain), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_vocabulary_domain_detail(request, domain_id: str):
    try:
        domain = MetadataVocabularyDomain.objects.prefetch_related("vocabularies").get(id=domain_id)
    except (ValidationError, MetadataVocabularyDomain.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        return JsonResponse(_vocabulary_domain_to_dict(domain))
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        name = str(payload.get("name") or "").strip()
        if not name:
            return JsonResponse({"error": "name is required"}, status=400)
        code = _normalize_code(name, payload.get("code"))
        if not code:
            return JsonResponse({"error": "code is required"}, status=400)
        domain.name = name
        domain.code = code
        domain.description = str(payload.get("description") or "").strip()
        domain.is_active = bool(payload.get("is_active", True))
        error = _save_model(domain)
        if error:
            return error
        domain.refresh_from_db()
        return JsonResponse(_vocabulary_domain_to_dict(domain))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_vocabularies(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        queryset = MetadataVocabulary.objects.select_related("domain").prefetch_related("items").order_by("name")
        search_term = str(request.GET.get("search") or request.GET.get("q") or "").strip()
        raw_domain_id = str(request.GET.get("domain_id") or "").strip()
        raw_domain_code = str(request.GET.get("domain_code") or "").strip()
        if raw_domain_id:
            queryset = queryset.filter(domain_id=raw_domain_id)
        if raw_domain_code:
            queryset = queryset.filter(domain__code=raw_domain_code)
        if search_term:
            queryset = queryset.filter(
                Q(name__icontains=search_term)
                | Q(code__icontains=search_term)
                | Q(description__icontains=search_term)
                | Q(domain__name__icontains=search_term)
                | Q(domain__code__icontains=search_term)
                | Q(items__label__icontains=search_term)
                | Q(items__value__icontains=search_term)
            ).distinct()
        items = [_vocabulary_to_dict(item) for item in queryset]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        vocabulary = MetadataVocabulary()
        error = _build_vocabulary_from_payload(vocabulary, payload)
        if error:
            return error
        error = _save_model(vocabulary)
        if error:
            return error
        error = _sync_vocabulary_items(vocabulary, payload.get("items"))
        if error:
            return error
        vocabulary.refresh_from_db()
        return JsonResponse(_vocabulary_to_dict(vocabulary), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_vocabulary_detail(request, vocabulary_id: str):
    try:
        vocabulary = MetadataVocabulary.objects.select_related("domain").prefetch_related("items").get(id=vocabulary_id)
    except (ValidationError, MetadataVocabulary.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        return JsonResponse(_vocabulary_to_dict(vocabulary))
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        error = _build_vocabulary_from_payload(vocabulary, payload)
        if error:
            return error
        error = _save_model(vocabulary)
        if error:
            return error
        error = _sync_vocabulary_items(vocabulary, payload.get("items"))
        if error:
            return error
        vocabulary.refresh_from_db()
        return JsonResponse(_vocabulary_to_dict(vocabulary))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_vocabulary_items(request, vocabulary_id: str):
    try:
        vocabulary = MetadataVocabulary.objects.select_related("domain").get(id=vocabulary_id)
    except (ValidationError, MetadataVocabulary.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method != "GET":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.metadata.view")
    if forbidden:
        return forbidden
    limit = _parse_positive_int_query(request, "limit", default=20, maximum=100)
    if isinstance(limit, JsonResponse):
        return limit
    offset = _parse_positive_int_query(request, "offset", default=0, maximum=10_000)
    if isinstance(offset, JsonResponse):
        return offset
    search_term = str(request.GET.get("search") or request.GET.get("q") or "").strip()
    include_inactive = str(request.GET.get("include_inactive") or "").strip().lower() in {"1", "true", "yes"}
    queryset = vocabulary.items.order_by("sort_order", "label")
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    if search_term:
        queryset = queryset.filter(Q(label__icontains=search_term) | Q(value__icontains=search_term))
    total_count = queryset.count()
    items = [_vocabulary_item_to_dict(item) for item in queryset[offset: offset + limit]]
    return JsonResponse(
        {
            "vocabulary": _vocabulary_to_dict(vocabulary),
            "items": items,
            "count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count,
        }
    )


@csrf_exempt
def lims_metadata_vocabulary_provision_defaults(request):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.metadata.manage")
    if forbidden:
        return forbidden
    summary = provision_default_metadata_vocabularies()
    return JsonResponse(
        {
            "status": "ok",
            **summary,
            "domains": MetadataVocabularyDomain.objects.count(),
            "vocabularies": MetadataVocabulary.objects.count(),
        }
    )


@csrf_exempt
def lims_metadata_field_definitions(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        items = [
            _field_definition_to_dict(item)
            for item in MetadataFieldDefinition.objects.select_related("vocabulary").order_by("name")
        ]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        field = MetadataFieldDefinition()
        error = _build_field_definition_from_payload(field, payload)
        if error:
            return error
        error = _save_model(field)
        if error:
            return error
        return JsonResponse(_field_definition_to_dict(field), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_field_definition_detail(request, definition_id: str):
    try:
        field = MetadataFieldDefinition.objects.select_related("vocabulary").get(id=definition_id)
    except (ValidationError, MetadataFieldDefinition.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        return JsonResponse(_field_definition_to_dict(field))
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        error = _build_field_definition_from_payload(field, payload)
        if error:
            return error
        error = _save_model(field)
        if error:
            return error
        return JsonResponse(_field_definition_to_dict(field))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_schemas(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        items = [
            _schema_to_dict(item)
            for item in MetadataSchema.objects.prefetch_related("versions__fields__vocabulary").order_by("name")
        ]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        schema = MetadataSchema()
        error = _build_schema_from_payload(schema, payload)
        if error:
            return error
        error = _save_model(schema)
        if error:
            return error
        initial_version = MetadataSchemaVersion(
            schema=schema,
            version_number=1,
            status=MetadataSchemaVersion.Status.DRAFT,
            change_summary=str(payload.get("change_summary") or "Initial draft").strip(),
        )
        error = _save_model(initial_version)
        if error:
            schema.delete()
            return error
        fields_payload = payload.get("fields")
        if fields_payload is not None:
            error = _sync_schema_version_fields(initial_version, fields_payload)
            if error:
                initial_version.delete()
                schema.delete()
                return error
        schema.refresh_from_db()
        return JsonResponse(_schema_to_dict(schema), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_schema_detail(request, schema_id: str):
    try:
        schema = MetadataSchema.objects.prefetch_related("versions__fields__vocabulary").get(id=schema_id)
    except (ValidationError, MetadataSchema.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        return JsonResponse(_schema_to_dict(schema))
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        error = _build_schema_from_payload(schema, payload)
        if error:
            return error
        error = _save_model(schema)
        if error:
            return error
        return JsonResponse(_schema_to_dict(schema))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_schema_versions(request, schema_id: str):
    try:
        schema = MetadataSchema.objects.get(id=schema_id)
    except (ValidationError, MetadataSchema.DoesNotExist):
        return JsonResponse({"error": "schema_not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        queryset = schema.versions.prefetch_related("fields__vocabulary").order_by("-version_number")
        status_filter = str(request.GET.get("status") or "").strip()
        if status_filter:
            if status_filter not in MetadataSchemaVersion.Status.values:
                return JsonResponse({"error": "invalid_status"}, status=400)
            queryset = queryset.filter(status=status_filter)
        items = [
            _schema_version_to_dict(item)
            for item in queryset
        ]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        if schema.versions.filter(status=MetadataSchemaVersion.Status.DRAFT).exists():
            return JsonResponse({"error": "draft_version_already_exists"}, status=409)
        fields_payload = payload.get("fields")
        source_version = None
        if payload.get("source_version_id"):
            try:
                source_version = MetadataSchemaVersion.objects.prefetch_related("fields__vocabulary").get(
                    id=payload["source_version_id"],
                    schema=schema,
                )
            except (ValidationError, MetadataSchemaVersion.DoesNotExist):
                return JsonResponse({"error": "source_version_not_found"}, status=404)
        version_number = payload.get("version_number")
        if version_number is None:
            latest_version = schema.versions.order_by("-version_number").first()
            version_number = (latest_version.version_number if latest_version else 0) + 1
        try:
            version_number = int(version_number)
        except (TypeError, ValueError):
            return JsonResponse({"error": "invalid_version_number"}, status=400)
        version = MetadataSchemaVersion(
            schema=schema,
            version_number=version_number,
            status=MetadataSchemaVersion.Status.DRAFT,
            change_summary=str(payload.get("change_summary") or "").strip(),
        )
        error = _save_model(version)
        if error:
            return error
        if fields_payload is not None:
            error = _sync_schema_version_fields(version, fields_payload)
            if error:
                version.delete()
                return error
        elif source_version is not None:
            _clone_schema_version_fields(source_version, version)
        version.refresh_from_db()
        return JsonResponse(_schema_version_to_dict(version), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_schema_version_detail(request, schema_id: str, version_id: str):
    try:
        version = MetadataSchemaVersion.objects.prefetch_related("fields__vocabulary").get(id=version_id, schema_id=schema_id)
    except (ValidationError, MetadataSchemaVersion.DoesNotExist):
        return JsonResponse({"error": "version_not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        return JsonResponse(_schema_version_to_dict(version))
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        if version.status != MetadataSchemaVersion.Status.DRAFT:
            return JsonResponse({"error": "published_versions_are_immutable"}, status=400)
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        if "change_summary" in payload:
            version.change_summary = str(payload.get("change_summary") or "").strip()
            error = _save_model(version)
            if error:
                return error
        if "fields" in payload:
            error = _sync_schema_version_fields(version, payload.get("fields"))
            if error:
                return error
        version.refresh_from_db()
        return JsonResponse(_schema_version_to_dict(version))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_schema_version_publish(request, schema_id: str, version_id: str):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.metadata.manage")
    if forbidden:
        return forbidden
    try:
        version = MetadataSchemaVersion.objects.get(id=version_id, schema_id=schema_id)
    except (ValidationError, MetadataSchemaVersion.DoesNotExist):
        return JsonResponse({"error": "version_not_found"}, status=404)
    if version.status != MetadataSchemaVersion.Status.DRAFT:
        return JsonResponse({"error": "only_draft_versions_can_be_published"}, status=400)
    if not version.fields.exists():
        return JsonResponse({"error": "version_requires_fields"}, status=400)
    MetadataSchemaVersion.objects.filter(schema_id=schema_id, status=MetadataSchemaVersion.Status.PUBLISHED).exclude(
        id=version.id
    ).update(status=MetadataSchemaVersion.Status.DEPRECATED)
    version.status = MetadataSchemaVersion.Status.PUBLISHED
    version.save(update_fields=["status", "updated_at"])
    version.refresh_from_db()
    return JsonResponse(_schema_version_to_dict(version))


@csrf_exempt
def lims_metadata_schema_bindings(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        queryset = MetadataSchemaBinding.objects.select_related("schema_version", "schema_version__schema").order_by(
            "target_type", "target_key"
        )
        if request.GET.get("target_type"):
            queryset = queryset.filter(target_type=request.GET["target_type"])
        if request.GET.get("target_key"):
            queryset = queryset.filter(target_key=request.GET["target_key"])
        items = [_schema_binding_to_dict(item) for item in queryset]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        schema_version, error = _resolve_optional_fk(
            MetadataSchemaVersion,
            payload.get("schema_version_id"),
            "schema_version_not_found",
        )
        if error:
            return error
        if schema_version is None:
            return JsonResponse({"error": "schema_version_id is required"}, status=400)
        if schema_version.status != MetadataSchemaVersion.Status.PUBLISHED:
            return JsonResponse({"error": "schema_version_must_be_published"}, status=400)
        target_type = str(payload.get("target_type") or "").strip()
        if target_type not in MetadataSchemaBinding.TargetType.values:
            return JsonResponse({"error": "invalid_target_type"}, status=400)
        target_key = str(payload.get("target_key") or "").strip()
        if not target_key:
            return JsonResponse({"error": "target_key is required"}, status=400)
        binding, _ = MetadataSchemaBinding.objects.get_or_create(
            target_type=target_type,
            target_key=target_key,
            defaults={"schema_version": schema_version},
        )
        binding.schema_version = schema_version
        binding.target_label = str(payload.get("target_label") or "").strip()
        binding.is_active = bool(payload.get("is_active", True))
        error = _save_model(binding)
        if error:
            return error
        binding.refresh_from_db()
        return JsonResponse(_schema_binding_to_dict(binding), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_validate(request):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.metadata.view")
    if forbidden:
        return forbidden
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"error": "invalid_json"}, status=400)
    data = payload.get("data")
    if not isinstance(data, dict):
        return JsonResponse({"error": "data must be an object"}, status=400)

    schema_version = None
    if payload.get("schema_version_id"):
        try:
            schema_version = MetadataSchemaVersion.objects.get(id=payload["schema_version_id"])
        except (ValidationError, MetadataSchemaVersion.DoesNotExist):
            return JsonResponse({"error": "schema_version_not_found"}, status=404)
    else:
        target_type = str(payload.get("target_type") or "").strip()
        target_key = str(payload.get("target_key") or "").strip()
        if not target_type or not target_key:
            return JsonResponse({"error": "schema_version_id or target binding is required"}, status=400)
        schema_version = resolve_schema_version_for_binding(target_type=target_type, target_key=target_key)
        if schema_version is None:
            return JsonResponse({"error": "binding_not_found"}, status=404)

    result = validate_metadata_payload(schema_version, data)
    return JsonResponse(
        {
            "valid": result.valid,
            "schema_version_id": str(schema_version.id),
            "schema_id": str(schema_version.schema_id),
            "errors": result.errors,
            "normalized_data": result.normalized_data,
        }
    )


def _build_biospecimen_type_from_payload(sample_type: BiospecimenType, payload: dict[str, object]):
    name = str(payload.get("name") or "").strip()
    key = str(payload.get("key") or "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)
    if not key:
        return JsonResponse({"error": "key is required"}, status=400)
    try:
        sequence_padding = int(payload.get("sequence_padding") or 6)
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_sequence_padding"}, status=400)
    sample_type.name = name
    sample_type.key = key
    sample_type.description = str(payload.get("description") or "").strip()
    sample_type.identifier_prefix = str(payload.get("identifier_prefix") or "SPEC").strip()
    sample_type.barcode_prefix = str(payload.get("barcode_prefix") or "BC").strip()
    sample_type.sequence_padding = sequence_padding
    if payload.get("next_sequence") is not None:
        try:
            sample_type.next_sequence = int(payload.get("next_sequence") or 1)
        except (TypeError, ValueError):
            return JsonResponse({"error": "invalid_next_sequence"}, status=400)
    sample_type.is_active = bool(payload.get("is_active", True))
    return None


def _build_biospecimen_from_payload(specimen: Biospecimen, payload: dict[str, object]):
    sample_type, error = _resolve_optional_fk(BiospecimenType, payload.get("sample_type_id"), "sample_type_not_found")
    if error:
        return error
    study, error = _resolve_optional_fk(Study, payload.get("study_id"), "study_not_found")
    if error:
        return error
    site, error = _resolve_optional_fk(Site, payload.get("site_id"), "site_not_found")
    if error:
        return error
    lab, error = _resolve_optional_fk(Lab, payload.get("lab_id"), "lab_not_found")
    if error:
        return error
    parent_specimen, error = _resolve_optional_fk(
        Biospecimen, payload.get("parent_specimen_id"), "parent_specimen_not_found"
    )
    if error:
        return error
    if sample_type is None:
        return JsonResponse({"error": "sample_type_id is required"}, status=400)
    quantity, error = _parse_decimal(payload.get("quantity"), field="quantity", default="0")
    if error:
        return error
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        return JsonResponse({"error": "metadata must be an object"}, status=400)

    specimen.sample_type = sample_type
    specimen.kind = str(payload.get("kind") or Biospecimen.Kind.PRIMARY)
    specimen.status = str(payload.get("status") or Biospecimen.Status.REGISTERED)
    specimen.subject_identifier = str(payload.get("subject_identifier") or "").strip()
    specimen.external_identifier = str(payload.get("external_identifier") or "").strip()
    specimen.study = study
    specimen.site = site
    specimen.lab = lab
    specimen.parent_specimen = parent_specimen
    specimen.lineage_root = parent_specimen.lineage_root if parent_specimen and parent_specimen.lineage_root_id else parent_specimen
    specimen.quantity = quantity
    specimen.quantity_unit = str(payload.get("quantity_unit") or "mL").strip()
    specimen.metadata = metadata
    specimen.is_active = bool(payload.get("is_active", True))
    return None


def _build_accessioning_manifest_from_payload(manifest: AccessioningManifest, payload: dict[str, object], *, request):
    sample_type, error = _resolve_optional_fk(BiospecimenType, payload.get("sample_type_id"), "sample_type_not_found")
    if error:
        return error
    study, error = _resolve_optional_fk(Study, payload.get("study_id"), "study_not_found")
    if error:
        return error
    site, error = _resolve_optional_fk(Site, payload.get("site_id"), "site_not_found")
    if error:
        return error
    lab, error = _resolve_optional_fk(Lab, payload.get("lab_id"), "lab_not_found")
    if error:
        return error
    if sample_type is None:
        return JsonResponse({"error": "sample_type_id is required"}, status=400)
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        return JsonResponse({"error": "metadata must be an object"}, status=400)
    manifest.sample_type = sample_type
    manifest.study = study
    manifest.site = site
    manifest.lab = lab
    manifest.source_system = str(payload.get("source_system") or "").strip()
    manifest.source_reference = str(payload.get("source_reference") or "").strip()
    manifest.notes = str(payload.get("notes") or "").strip()
    manifest.metadata = metadata
    manifest.created_by = str(getattr(request, "auth_user_id", None) or request.headers.get("X-User-Id", "")).strip()
    if not manifest.manifest_identifier:
        manifest.manifest_identifier = str(payload.get("manifest_identifier") or "").strip() or generate_manifest_identifier()
    return None


def _build_manifest_item_from_payload(item: AccessioningManifestItem, payload: dict[str, object]):
    biospecimen, error = _resolve_optional_fk(Biospecimen, payload.get("biospecimen_id"), "biospecimen_not_found")
    if error:
        return error
    quantity, error = _parse_decimal(payload.get("quantity"), field="quantity", default="0")
    if error:
        return error
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        return JsonResponse({"error": "metadata must be an object"}, status=400)
    try:
        position = int(payload.get("position") or item.position or 1)
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_position"}, status=400)
    item.biospecimen = biospecimen
    item.position = position
    item.expected_subject_identifier = str(payload.get("expected_subject_identifier") or "").strip()
    item.expected_sample_identifier = str(payload.get("expected_sample_identifier") or "").strip()
    item.expected_barcode = str(payload.get("expected_barcode") or "").strip()
    item.quantity = quantity
    item.quantity_unit = str(payload.get("quantity_unit") or "mL").strip()
    item.collection_status = str(payload.get("collection_status") or "").strip()
    item.notes = str(payload.get("notes") or "").strip()
    item.metadata = metadata
    return None


def _accessioning_error_response(exc: AccessioningError):
    message = str(exc)
    if message.startswith("metadata_invalid:"):
        try:
            errors = json.loads(message.split(":", 1)[1])
        except json.JSONDecodeError:
            errors = []
        return JsonResponse({"error": "metadata_invalid", "errors": errors}, status=400)
    return JsonResponse({"error": message}, status=400)


def _batch_plate_error_response(exc: BatchPlateError):
    return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def lims_biospecimen_types(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.artifact.view")
        if forbidden:
            return forbidden
        items = [_biospecimen_type_to_dict(item) for item in BiospecimenType.objects.order_by("name")]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.artifact.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        sample_type = BiospecimenType()
        error = _build_biospecimen_type_from_payload(sample_type, payload)
        if error:
            return error
        error = _save_model(sample_type)
        if error:
            return error
        return JsonResponse(_biospecimen_type_to_dict(sample_type), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_biospecimen_type_detail(request, sample_type_id: str):
    try:
        sample_type = BiospecimenType.objects.get(id=sample_type_id)
    except (ValidationError, BiospecimenType.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.artifact.view")
        if forbidden:
            return forbidden
        return JsonResponse(_biospecimen_type_to_dict(sample_type))
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.artifact.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        error = _build_biospecimen_type_from_payload(sample_type, payload)
        if error:
            return error
        error = _save_model(sample_type)
        if error:
            return error
        return JsonResponse(_biospecimen_type_to_dict(sample_type))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_biospecimens(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.artifact.view")
        if forbidden:
            return forbidden
        queryset = Biospecimen.objects.select_related(
            "sample_type", "study", "site", "lab", "parent_specimen", "lineage_root"
        ).prefetch_related("aliquots", "pool_memberships").order_by("-created_at")
        if request.GET.get("sample_type_id"):
            queryset = queryset.filter(sample_type_id=request.GET["sample_type_id"])
        if request.GET.get("status"):
            queryset = queryset.filter(status=request.GET["status"])
        if request.GET.get("subject_identifier"):
            queryset = queryset.filter(subject_identifier=request.GET["subject_identifier"])
        items = [_biospecimen_to_dict(item) for item in queryset[:200]]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.artifact.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        specimen = Biospecimen()
        error = _build_biospecimen_from_payload(specimen, payload)
        if error:
            return error
        if not specimen.sample_identifier:
            sample_identifier, barcode = allocate_biospecimen_identifiers(specimen.sample_type)
            specimen.sample_identifier = sample_identifier
            specimen.barcode = barcode
        error = _save_model(specimen)
        if error:
            return error
        specimen.refresh_from_db()
        return JsonResponse(_biospecimen_to_dict(specimen), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_biospecimen_detail(request, specimen_id: str):
    try:
        specimen = Biospecimen.objects.select_related(
            "sample_type", "study", "site", "lab", "parent_specimen", "lineage_root"
        ).prefetch_related("aliquots", "pool_memberships").get(id=specimen_id)
    except (ValidationError, Biospecimen.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.artifact.view")
        if forbidden:
            return forbidden
        return JsonResponse(_biospecimen_to_dict(specimen))
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.artifact.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        sample_identifier = specimen.sample_identifier
        barcode = specimen.barcode
        error = _build_biospecimen_from_payload(specimen, payload)
        if error:
            return error
        specimen.sample_identifier = sample_identifier
        specimen.barcode = barcode
        error = _save_model(specimen)
        if error:
            return error
        specimen.refresh_from_db()
        return JsonResponse(_biospecimen_to_dict(specimen))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_biospecimen_transition(request, specimen_id: str):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.manage")
    if forbidden:
        return forbidden
    try:
        specimen = Biospecimen.objects.get(id=specimen_id)
    except (ValidationError, Biospecimen.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"error": "invalid_json"}, status=400)
    next_status = str(payload.get("status") or "").strip()
    if next_status not in Biospecimen.Status.values:
        return JsonResponse({"error": "invalid_status"}, status=400)
    try:
        transition_biospecimen(specimen, next_status)
    except BiospecimenTransitionError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    specimen.refresh_from_db()
    return JsonResponse(_biospecimen_to_dict(specimen))


@csrf_exempt
def lims_biospecimen_aliquots(request, specimen_id: str):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.manage")
    if forbidden:
        return forbidden
    try:
        specimen = Biospecimen.objects.get(id=specimen_id)
    except (ValidationError, Biospecimen.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"error": "invalid_json"}, status=400)
    try:
        count = int(payload.get("count") or 1)
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_count"}, status=400)
    quantity, error = _parse_decimal(payload.get("quantity"), field="quantity", default="0")
    if error:
        return error
    quantity_unit = str(payload.get("quantity_unit") or specimen.quantity_unit or "mL").strip()
    try:
        items = create_aliquots(specimen, count=count, quantity=quantity, quantity_unit=quantity_unit)
    except BiospecimenTransitionError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"items": [_biospecimen_to_dict(item) for item in items]}, status=201)


@csrf_exempt
def lims_biospecimen_pools(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.artifact.view")
        if forbidden:
            return forbidden
        queryset = BiospecimenPool.objects.select_related("sample_type", "study", "site", "lab").prefetch_related(
            "members"
        ).order_by("-created_at")
        if request.GET.get("sample_type_id"):
            queryset = queryset.filter(sample_type_id=request.GET["sample_type_id"])
        if request.GET.get("status"):
            queryset = queryset.filter(status=request.GET["status"])
        items = [_biospecimen_pool_to_dict(item) for item in queryset[:200]]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.artifact.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        sample_type, error = _resolve_optional_fk(BiospecimenType, payload.get("sample_type_id"), "sample_type_not_found")
        if error:
            return error
        if sample_type is None:
            return JsonResponse({"error": "sample_type_id is required"}, status=400)
        study, error = _resolve_optional_fk(Study, payload.get("study_id"), "study_not_found")
        if error:
            return error
        site, error = _resolve_optional_fk(Site, payload.get("site_id"), "site_not_found")
        if error:
            return error
        lab, error = _resolve_optional_fk(Lab, payload.get("lab_id"), "lab_not_found")
        if error:
            return error
        specimen_ids = payload.get("specimen_ids")
        if not isinstance(specimen_ids, list) or not specimen_ids:
            return JsonResponse({"error": "specimen_ids must be a non-empty list"}, status=400)
        specimens = list(Biospecimen.objects.filter(id__in=specimen_ids))
        if len(specimens) != len(specimen_ids):
            return JsonResponse({"error": "specimen_not_found"}, status=404)
        quantity, error = _parse_decimal(payload.get("quantity"), field="quantity", default="0")
        if error:
            return error
        quantity_unit = str(payload.get("quantity_unit") or "mL").strip()
        metadata = payload.get("metadata") or {}
        if not isinstance(metadata, dict):
            return JsonResponse({"error": "metadata must be an object"}, status=400)
        try:
            pool = create_pool(
                sample_type=sample_type,
                specimens=specimens,
                quantity=quantity,
                quantity_unit=quantity_unit,
                study=study,
                site=site,
                lab=lab,
                metadata=metadata,
            )
        except BiospecimenTransitionError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        pool.refresh_from_db()
        return JsonResponse(_biospecimen_pool_to_dict(pool), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_biospecimen_pool_detail(request, pool_id: str):
    try:
        pool = BiospecimenPool.objects.select_related("sample_type", "study", "site", "lab").prefetch_related(
            "members"
        ).get(id=pool_id)
    except (ValidationError, BiospecimenPool.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.artifact.view")
        if forbidden:
            return forbidden
        return JsonResponse(_biospecimen_pool_to_dict(pool))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_biospecimen_pool_transition(request, pool_id: str):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.manage")
    if forbidden:
        return forbidden
    try:
        pool = BiospecimenPool.objects.get(id=pool_id)
    except (ValidationError, BiospecimenPool.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"error": "invalid_json"}, status=400)
    next_status = str(payload.get("status") or "").strip()
    if next_status not in BiospecimenPool.Status.values:
        return JsonResponse({"error": "invalid_status"}, status=400)
    try:
        transition_pool(pool, next_status)
    except BiospecimenTransitionError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    pool.refresh_from_db()
    return JsonResponse(_biospecimen_pool_to_dict(pool))


@csrf_exempt
def lims_accessioning_receive_single(request):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.manage")
    if forbidden:
        return forbidden
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"error": "invalid_json"}, status=400)
    sample_type, error = _resolve_optional_fk(BiospecimenType, payload.get("sample_type_id"), "sample_type_not_found")
    if error:
        return error
    if sample_type is None:
        return JsonResponse({"error": "sample_type_id is required"}, status=400)
    study, error = _resolve_optional_fk(Study, payload.get("study_id"), "study_not_found")
    if error:
        return error
    site, error = _resolve_optional_fk(Site, payload.get("site_id"), "site_not_found")
    if error:
        return error
    lab, error = _resolve_optional_fk(Lab, payload.get("lab_id"), "lab_not_found")
    if error:
        return error
    quantity, error = _parse_decimal(payload.get("quantity"), field="quantity", default="0")
    if error:
        return error
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        return JsonResponse({"error": "metadata must be an object"}, status=400)
    receipt_context = payload.get("receipt_context") or {}
    if not isinstance(receipt_context, dict):
        return JsonResponse({"error": "receipt_context must be an object"}, status=400)
    received_at, error = _parse_optional_received_at(payload.get("received_at"))
    if error:
        return error
    try:
        specimen, event = receive_single_biospecimen(
            sample_type=sample_type,
            study=study,
            site=site,
            lab=lab,
            subject_identifier=str(payload.get("subject_identifier") or "").strip(),
            external_identifier=str(payload.get("external_identifier") or "").strip(),
            quantity=quantity,
            quantity_unit=str(payload.get("quantity_unit") or "mL").strip(),
            metadata=metadata,
            received_by=str(getattr(request, "auth_user_id", None) or request.headers.get("X-User-Id", "")).strip(),
            sample_identifier=str(payload.get("sample_identifier") or "").strip(),
            barcode=str(payload.get("barcode") or "").strip(),
            scan_value=str(payload.get("scan_value") or "").strip(),
            notes=str(payload.get("notes") or "").strip(),
            receipt_context=receipt_context,
            received_at=received_at,
        )
    except AccessioningError as exc:
        return _accessioning_error_response(exc)
    specimen.refresh_from_db()
    return JsonResponse({"biospecimen": _biospecimen_to_dict(specimen), "event": _receiving_event_to_dict(event)}, status=201)


@csrf_exempt
def lims_accessioning_manifests(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.artifact.view")
        if forbidden:
            return forbidden
        queryset = AccessioningManifest.objects.select_related("sample_type", "study", "site", "lab").prefetch_related(
            "items"
        ).order_by("-created_at")
        if request.GET.get("status"):
            queryset = queryset.filter(status=request.GET["status"])
        if request.GET.get("sample_type_id"):
            queryset = queryset.filter(sample_type_id=request.GET["sample_type_id"])
        items = [_accessioning_manifest_to_dict(item) for item in queryset[:200]]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.artifact.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        manifest = AccessioningManifest()
        error = _build_accessioning_manifest_from_payload(manifest, payload, request=request)
        if error:
            return error
        error = _save_model(manifest)
        if error:
            return error
        items_payload = payload.get("items") or []
        if not isinstance(items_payload, list):
            return JsonResponse({"error": "items must be a list"}, status=400)
        for index, item_payload in enumerate(items_payload, start=1):
            if not isinstance(item_payload, dict):
                return JsonResponse({"error": "item must be an object"}, status=400)
            item = AccessioningManifestItem(manifest=manifest, position=index)
            error = _build_manifest_item_from_payload(item, {**item_payload, "position": item_payload.get("position") or index})
            if error:
                manifest.delete()
                return error
            error = _save_model(item)
            if error:
                manifest.delete()
                return error
        if bool(payload.get("submit", False)):
            try:
                submit_manifest(manifest)
            except AccessioningError as exc:
                return _accessioning_error_response(exc)
        manifest.refresh_from_db()
        return JsonResponse(_accessioning_manifest_to_dict(manifest), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_accessioning_manifest_detail(request, manifest_id: str):
    try:
        manifest = AccessioningManifest.objects.select_related("sample_type", "study", "site", "lab").prefetch_related(
            "items"
        ).get(id=manifest_id)
    except (ValidationError, AccessioningManifest.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.artifact.view")
        if forbidden:
            return forbidden
        return JsonResponse(
            {
                **_accessioning_manifest_to_dict(manifest),
                "items": [_manifest_item_to_dict(item) for item in manifest.items.order_by("position", "created_at")],
            }
        )
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.artifact.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        error = _build_accessioning_manifest_from_payload(manifest, payload, request=request)
        if error:
            return error
        error = _save_model(manifest)
        if error:
            return error
        manifest.refresh_from_db()
        return JsonResponse(_accessioning_manifest_to_dict(manifest))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_accessioning_manifest_submit(request, manifest_id: str):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.manage")
    if forbidden:
        return forbidden
    try:
        manifest = AccessioningManifest.objects.get(id=manifest_id)
    except (ValidationError, AccessioningManifest.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    try:
        submit_manifest(manifest)
    except AccessioningError as exc:
        return _accessioning_error_response(exc)
    manifest.refresh_from_db()
    return JsonResponse(_accessioning_manifest_to_dict(manifest))


@csrf_exempt
def lims_accessioning_manifest_item_receive(request, manifest_id: str, item_id: str):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.manage")
    if forbidden:
        return forbidden
    try:
        item = AccessioningManifestItem.objects.select_related("manifest", "biospecimen", "manifest__sample_type").get(
            id=item_id, manifest_id=manifest_id
        )
    except (ValidationError, AccessioningManifestItem.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"error": "invalid_json"}, status=400)
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        return JsonResponse({"error": "metadata must be an object"}, status=400)
    receipt_context = payload.get("receipt_context") or {}
    if not isinstance(receipt_context, dict):
        return JsonResponse({"error": "receipt_context must be an object"}, status=400)
    received_at, error = _parse_optional_received_at(payload.get("received_at"))
    if error:
        return error
    try:
        item, event = receive_manifest_item(
            item,
            received_by=str(getattr(request, "auth_user_id", None) or request.headers.get("X-User-Id", "")).strip(),
            scan_value=str(payload.get("scan_value") or "").strip(),
            notes=str(payload.get("notes") or "").strip(),
            metadata=metadata,
            receipt_context=receipt_context,
            received_at=received_at,
        )
    except AccessioningError as exc:
        return _accessioning_error_response(exc)
    item.refresh_from_db()
    return JsonResponse({"item": _manifest_item_to_dict(item), "event": _receiving_event_to_dict(event)})


@csrf_exempt
def lims_accessioning_manifest_report(request, manifest_id: str):
    if request.method != "GET":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.view")
    if forbidden:
        return forbidden
    try:
        manifest = AccessioningManifest.objects.select_related("sample_type", "study", "site", "lab").get(id=manifest_id)
    except (ValidationError, AccessioningManifest.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    return JsonResponse(accessioning_report(manifest))


@csrf_exempt
def lims_receiving_discrepancies(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.artifact.view")
        if forbidden:
            return forbidden
        queryset = ReceivingDiscrepancy.objects.select_related("manifest", "manifest_item", "biospecimen").order_by(
            "-created_at"
        )
        if request.GET.get("manifest_id"):
            queryset = queryset.filter(manifest_id=request.GET["manifest_id"])
        if request.GET.get("status"):
            queryset = queryset.filter(status=request.GET["status"])
        items = [_receiving_discrepancy_to_dict(item) for item in queryset[:200]]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.artifact.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        manifest, error = _resolve_optional_fk(AccessioningManifest, payload.get("manifest_id"), "manifest_not_found")
        if error:
            return error
        item, error = _resolve_optional_fk(AccessioningManifestItem, payload.get("manifest_item_id"), "manifest_item_not_found")
        if error:
            return error
        biospecimen, error = _resolve_optional_fk(Biospecimen, payload.get("biospecimen_id"), "biospecimen_not_found")
        if error:
            return error
        code = str(payload.get("code") or "").strip()
        if code not in ReceivingDiscrepancy.Code.values:
            return JsonResponse({"error": "invalid_code"}, status=400)
        expected_data = payload.get("expected_data") or {}
        actual_data = payload.get("actual_data") or {}
        if not isinstance(expected_data, dict) or not isinstance(actual_data, dict):
            return JsonResponse({"error": "expected_data and actual_data must be objects"}, status=400)
        try:
            discrepancy = create_receiving_discrepancy(
                code=code,
                recorded_by=str(getattr(request, "auth_user_id", None) or request.headers.get("X-User-Id", "")).strip(),
                manifest=manifest,
                manifest_item=item,
                biospecimen=biospecimen,
                notes=str(payload.get("notes") or "").strip(),
                expected_data=expected_data,
                actual_data=actual_data,
            )
        except AccessioningError as exc:
            return _accessioning_error_response(exc)
        return JsonResponse(_receiving_discrepancy_to_dict(discrepancy), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_plate_layouts(request):
    if request.method != "GET":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.view")
    if forbidden:
        return forbidden
    items = [_plate_layout_to_dict(item) for item in PlateLayoutTemplate.objects.filter(is_active=True).order_by("rows", "columns")]
    return JsonResponse({"items": items})


@csrf_exempt
def lims_plate_layout_detail(request, layout_id: str):
    if request.method != "GET":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.view")
    if forbidden:
        return forbidden
    try:
        layout = PlateLayoutTemplate.objects.get(id=layout_id)
    except (ValidationError, PlateLayoutTemplate.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    return JsonResponse(_plate_layout_to_dict(layout))


@csrf_exempt
def lims_processing_batches(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.artifact.view")
        if forbidden:
            return forbidden
        queryset = ProcessingBatch.objects.select_related("sample_type", "study", "site", "lab").prefetch_related(
            "plates", "plates__assignments"
        ).order_by("-created_at")
        if request.GET.get("status"):
            queryset = queryset.filter(status=request.GET["status"])
        if request.GET.get("sample_type_id"):
            queryset = queryset.filter(sample_type_id=request.GET["sample_type_id"])
        items = [_processing_batch_to_dict(item) for item in queryset[:200]]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.artifact.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        sample_type, error = _resolve_optional_fk(BiospecimenType, payload.get("sample_type_id"), "sample_type_not_found")
        if error:
            return error
        if sample_type is None:
            return JsonResponse({"error": "sample_type_id is required"}, status=400)
        study, error = _resolve_optional_fk(Study, payload.get("study_id"), "study_not_found")
        if error:
            return error
        site, error = _resolve_optional_fk(Site, payload.get("site_id"), "site_not_found")
        if error:
            return error
        lab, error = _resolve_optional_fk(Lab, payload.get("lab_id"), "lab_not_found")
        if error:
            return error
        metadata = payload.get("metadata") or {}
        if not isinstance(metadata, dict):
            return JsonResponse({"error": "metadata must be an object"}, status=400)
        plates_payload = payload.get("plates") or []
        if not isinstance(plates_payload, list):
            return JsonResponse({"error": "plates must be a list"}, status=400)
        prepared_plates: list[dict[str, object]] = []
        for plate_payload in plates_payload:
            if not isinstance(plate_payload, dict):
                return JsonResponse({"error": "plate must be an object"}, status=400)
            layout_template, error = _resolve_optional_fk(
                PlateLayoutTemplate,
                plate_payload.get("layout_template_id"),
                "plate_layout_not_found",
            )
            if error:
                return error
            if layout_template is None:
                return JsonResponse({"error": "layout_template_id is required"}, status=400)
            plate_metadata = plate_payload.get("metadata") or {}
            if not isinstance(plate_metadata, dict):
                return JsonResponse({"error": "plate metadata must be an object"}, status=400)
            assignments_payload = plate_payload.get("assignments") or []
            if not isinstance(assignments_payload, list):
                return JsonResponse({"error": "assignments must be a list"}, status=400)
            prepared_assignments: list[dict[str, object]] = []
            for assignment_payload in assignments_payload:
                if not isinstance(assignment_payload, dict):
                    return JsonResponse({"error": "assignment must be an object"}, status=400)
                biospecimen, error = _resolve_optional_fk(
                    Biospecimen,
                    assignment_payload.get("biospecimen_id"),
                    "biospecimen_not_found",
                )
                if error:
                    return error
                if biospecimen is None:
                    return JsonResponse({"error": "biospecimen_id is required"}, status=400)
                assignment_metadata = assignment_payload.get("metadata") or {}
                if not isinstance(assignment_metadata, dict):
                    return JsonResponse({"error": "assignment metadata must be an object"}, status=400)
                raw_position = assignment_payload.get("position_index")
                if raw_position in ("", None):
                    position_index = None
                else:
                    try:
                        position_index = int(raw_position)
                    except (TypeError, ValueError):
                        return JsonResponse({"error": "invalid_position_index"}, status=400)
                prepared_assignments.append(
                    {
                        "biospecimen": biospecimen,
                        "position_index": position_index,
                        "well_label": str(assignment_payload.get("well_label") or "").strip(),
                        "metadata": assignment_metadata,
                    }
                )
            prepared_plates.append(
                {
                    "layout_template": layout_template,
                    "label": str(plate_payload.get("label") or "").strip(),
                    "metadata": plate_metadata,
                    "assignments": prepared_assignments,
                }
            )
        try:
            batch = create_processing_batch(
                sample_type=sample_type,
                plates=prepared_plates,
                study=study,
                site=site,
                lab=lab,
                notes=str(payload.get("notes") or "").strip(),
                metadata=metadata,
                created_by=str(getattr(request, "auth_user_id", None) or request.headers.get("X-User-Id", "")).strip(),
            )
        except BatchPlateError as exc:
            return _batch_plate_error_response(exc)
        batch.refresh_from_db()
        return JsonResponse(_processing_batch_to_dict(batch, include_plates=True), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_processing_batch_detail(request, batch_id: str):
    try:
        batch = ProcessingBatch.objects.select_related("sample_type", "study", "site", "lab").prefetch_related(
            "plates", "plates__layout_template", "plates__assignments", "plates__assignments__biospecimen"
        ).get(id=batch_id)
    except (ValidationError, ProcessingBatch.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.artifact.view")
        if forbidden:
            return forbidden
        return JsonResponse(_processing_batch_to_dict(batch, include_plates=True))
    if request.method == "PUT":
        forbidden = require_lims_permission(request, "lims.artifact.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        study, error = _resolve_optional_fk(Study, payload.get("study_id"), "study_not_found")
        if error:
            return error
        site, error = _resolve_optional_fk(Site, payload.get("site_id"), "site_not_found")
        if error:
            return error
        lab, error = _resolve_optional_fk(Lab, payload.get("lab_id"), "lab_not_found")
        if error:
            return error
        metadata = payload.get("metadata", batch.metadata)
        if not isinstance(metadata, dict):
            return JsonResponse({"error": "metadata must be an object"}, status=400)
        batch.study = study
        batch.site = site
        batch.lab = lab
        batch.notes = str(payload.get("notes", batch.notes) or "").strip()
        batch.metadata = metadata
        error = _save_model(batch)
        if error:
            return error
        batch.refresh_from_db()
        return JsonResponse(_processing_batch_to_dict(batch, include_plates=True))
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_processing_batch_transition(request, batch_id: str):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.manage")
    if forbidden:
        return forbidden
    try:
        batch = ProcessingBatch.objects.get(id=batch_id)
    except (ValidationError, ProcessingBatch.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"error": "invalid_json"}, status=400)
    next_status = str(payload.get("status") or "").strip()
    if next_status not in ProcessingBatch.Status.values:
        return JsonResponse({"error": "invalid_status"}, status=400)
    try:
        transition_processing_batch(batch, next_status)
    except BatchPlateError as exc:
        return _batch_plate_error_response(exc)
    batch.refresh_from_db()
    return JsonResponse(_processing_batch_to_dict(batch))


@csrf_exempt
def lims_processing_batch_worksheet(request, batch_id: str):
    if request.method != "GET":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.view")
    if forbidden:
        return forbidden
    try:
        batch = ProcessingBatch.objects.select_related("sample_type", "study", "site", "lab").prefetch_related(
            "plates", "plates__layout_template", "plates__assignments", "plates__assignments__biospecimen"
        ).get(id=batch_id)
    except (ValidationError, ProcessingBatch.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    return JsonResponse(processing_batch_worksheet(batch))


@csrf_exempt
def lims_processing_batch_worksheet_print_job(request, batch_id: str):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    forbidden = require_lims_permission(request, "lims.artifact.manage")
    if forbidden:
        return forbidden
    try:
        batch = ProcessingBatch.objects.select_related("sample_type", "study", "site", "lab").prefetch_related(
            "plates", "plates__layout_template", "plates__assignments", "plates__assignments__biospecimen"
        ).get(id=batch_id)
    except (ValidationError, ProcessingBatch.DoesNotExist):
        return JsonResponse({"error": "not_found"}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        payload = {}
    try:
        print_job = create_processing_batch_worksheet_job(
            batch,
            destination=str(payload.get("destination") or "worksheet-preview").strip(),
            template_ref=str(payload.get("template_ref") or "a4/batch-rows").strip(),
            output_format=str(payload.get("output_format") or "pdf").strip(),
            pdf_sheet_preset=str(payload.get("pdf_sheet_preset") or "a4-38x21.2").strip(),
        )
    except BatchPlateError as exc:
        return _batch_plate_error_response(exc)
    batch.refresh_from_db()
    return JsonResponse(
        {
            "batch": _processing_batch_to_dict(batch),
            "print_job": _print_job_summary_to_dict(print_job),
        },
        status=201,
    )
