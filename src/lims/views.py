import json
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from core.identity import request_roles

from .permissions import permission_summary_for_roles, require_lims_permission
from .models import (
    Biospecimen,
    BiospecimenPool,
    BiospecimenType,
    Lab,
    MetadataFieldDefinition,
    MetadataSchema,
    MetadataSchemaBinding,
    MetadataSchemaField,
    MetadataSchemaVersion,
    MetadataVocabulary,
    MetadataVocabularyItem,
    Site,
    Study,
    TanzaniaAddressSyncRun,
    TanzaniaDistrict,
    TanzaniaRegion,
    TanzaniaStreet,
    TanzaniaWard,
)
from .services import (
    allocate_biospecimen_identifiers,
    BiospecimenTransitionError,
    create_aliquots,
    create_pool,
    resolve_schema_version_for_binding,
    sync_run_to_dict,
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


def _dashboard_payload(request) -> dict[str, object]:
    return {
        'service_key': 'lims',
        'tenant_schema': _user_context(request)['tenant_schema'],
        'cards': {
            'workflows': 0,
            'queues': 0,
            'instruments': 0,
        },
        'launchpad': [
            {
                'title': 'Reference data',
                'description': 'Prepare lab, study, and site structures for tenant onboarding.',
                'status': 'planned',
            },
            {
                'title': 'Workflow configuration',
                'description': 'Design draft/publish workflow templates and metadata schemas.',
                'status': 'planned',
            },
            {
                'title': 'Operator workspace',
                'description': 'Provide inbox, receiving, QC, and storage entrypoints.',
                'status': 'planned',
            },
        ],
    }


def _parse_json_body(request):
    try:
        body = request.body.decode("utf-8") if request.body else ""
        return json.loads(body or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _model_to_option(item, label_attr: str = "name") -> dict[str, str]:
    return {"value": str(item.id), "label": getattr(item, label_attr)}


def _lab_to_dict(lab: Lab) -> dict[str, object]:
    return {
        "id": str(lab.id),
        "name": lab.name,
        "code": lab.code,
        "description": lab.description,
        "address_line": lab.address_line,
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
        "status": study.status,
    }


def _site_to_dict(site: Site) -> dict[str, object]:
    return {
        "id": str(site.id),
        "name": site.name,
        "code": site.code,
        "description": site.description,
        "study_id": str(site.study_id) if site.study_id else None,
        "lab_id": str(site.lab_id) if site.lab_id else None,
        "address_line": site.address_line,
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


def _vocabulary_item_to_dict(item: MetadataVocabularyItem) -> dict[str, object]:
    return {
        "id": str(item.id),
        "value": item.value,
        "label": item.label,
        "sort_order": item.sort_order,
        "is_active": item.is_active,
    }


def _vocabulary_to_dict(vocabulary: MetadataVocabulary) -> dict[str, object]:
    return {
        "id": str(vocabulary.id),
        "name": vocabulary.name,
        "code": vocabulary.code,
        "description": vocabulary.description,
        "is_active": vocabulary.is_active,
        "items": [_vocabulary_item_to_dict(item) for item in vocabulary.items.order_by("sort_order", "label")],
    }


def _field_definition_to_dict(field: MetadataFieldDefinition) -> dict[str, object]:
    return {
        "id": str(field.id),
        "name": field.name,
        "code": field.code,
        "description": field.description,
        "field_type": field.field_type,
        "help_text": field.help_text,
        "placeholder": field.placeholder,
        "vocabulary_id": str(field.vocabulary_id) if field.vocabulary_id else None,
        "default_value": field.default_value,
        "config": field.config,
        "is_active": field.is_active,
    }


def _schema_field_to_dict(field: MetadataSchemaField) -> dict[str, object]:
    return {
        "id": str(field.id),
        "field_definition_id": str(field.field_definition_id),
        "field_definition_code": field.field_definition.code,
        "field_definition_name": field.field_definition.name,
        "field_type": field.field_definition.field_type,
        "field_key": field.field_key,
        "position": field.position,
        "required": field.required,
        "validation_rules": dict(field.validation_rules or {}),
        "condition": dict(field.condition or {}),
    }


def _schema_version_to_dict(version: MetadataSchemaVersion) -> dict[str, object]:
    return {
        "id": str(version.id),
        "schema_id": str(version.schema_id),
        "version_number": version.version_number,
        "status": version.status,
        "change_summary": version.change_summary,
        "fields": [_schema_field_to_dict(item) for item in version.fields.select_related("field_definition").order_by("position", "field_key")],
    }


def _schema_to_dict(schema: MetadataSchema) -> dict[str, object]:
    return {
        "id": str(schema.id),
        "name": schema.name,
        "code": schema.code,
        "description": schema.description,
        "is_active": schema.is_active,
        "versions": [_schema_version_to_dict(item) for item in schema.versions.order_by("-version_number")],
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


def _build_lab_from_payload(lab: Lab, payload: dict[str, object]):
    region, error = _resolve_optional_fk(TanzaniaRegion, payload.get("region_id"), "region_not_found")
    if error:
        return error
    district, error = _resolve_optional_fk(TanzaniaDistrict, payload.get("district_id"), "district_not_found")
    if error:
        return error
    ward, error = _resolve_optional_fk(TanzaniaWard, payload.get("ward_id"), "ward_not_found")
    if error:
        return error
    street, error = _resolve_optional_fk(TanzaniaStreet, payload.get("street_id"), "street_not_found")
    if error:
        return error

    if not payload.get("name"):
        return JsonResponse({"error": "name is required"}, status=400)

    lab.name = str(payload.get("name")).strip()
    lab.code = str(payload.get("code") or "").strip()
    lab.description = str(payload.get("description") or "").strip()
    lab.address_line = str(payload.get("address_line") or "").strip()
    lab.region = region
    lab.district = district
    lab.ward = ward
    lab.street = street
    lab.postcode = str(payload.get("postcode") or "").strip()
    lab.is_active = bool(payload.get("is_active", True))
    return None


def _build_study_from_payload(study: Study, payload: dict[str, object]):
    lead_lab, error = _resolve_optional_fk(Lab, payload.get("lead_lab_id"), "lab_not_found")
    if error:
        return error
    if not payload.get("name"):
        return JsonResponse({"error": "name is required"}, status=400)
    study.name = str(payload.get("name")).strip()
    study.code = str(payload.get("code") or "").strip()
    study.description = str(payload.get("description") or "").strip()
    study.sponsor = str(payload.get("sponsor") or "").strip()
    study.lead_lab = lead_lab
    status = str(payload.get("status") or Study.Status.ACTIVE)
    if status not in Study.Status.values:
        return JsonResponse({"error": "invalid_status"}, status=400)
    study.status = status
    return None


def _build_site_from_payload(site: Site, payload: dict[str, object]):
    study, error = _resolve_optional_fk(Study, payload.get("study_id"), "study_not_found")
    if error:
        return error
    lab, error = _resolve_optional_fk(Lab, payload.get("lab_id"), "lab_not_found")
    if error:
        return error
    region, error = _resolve_optional_fk(TanzaniaRegion, payload.get("region_id"), "region_not_found")
    if error:
        return error
    district, error = _resolve_optional_fk(TanzaniaDistrict, payload.get("district_id"), "district_not_found")
    if error:
        return error
    ward, error = _resolve_optional_fk(TanzaniaWard, payload.get("ward_id"), "ward_not_found")
    if error:
        return error
    street, error = _resolve_optional_fk(TanzaniaStreet, payload.get("street_id"), "street_not_found")
    if error:
        return error
    if not payload.get("name"):
        return JsonResponse({"error": "name is required"}, status=400)
    site.name = str(payload.get("name")).strip()
    site.code = str(payload.get("code") or "").strip()
    site.description = str(payload.get("description") or "").strip()
    site.study = study
    site.lab = lab
    site.address_line = str(payload.get("address_line") or "").strip()
    site.region = region
    site.district = district
    site.ward = ward
    site.street = street
    site.postcode = str(payload.get("postcode") or "").strip()
    site.is_active = bool(payload.get("is_active", True))
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


def _build_vocabulary_from_payload(vocabulary: MetadataVocabulary, payload: dict[str, object]):
    if not payload.get("name"):
        return JsonResponse({"error": "name is required"}, status=400)
    if not payload.get("code"):
        return JsonResponse({"error": "code is required"}, status=400)
    vocabulary.name = str(payload.get("name")).strip()
    vocabulary.code = str(payload.get("code")).strip()
    vocabulary.description = str(payload.get("description") or "").strip()
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
    schema.is_active = bool(payload.get("is_active", True))
    return None


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
    return render(
        request,
        'lims/dashboard.html',
        {
            'active_nav': 'lims',
            'payload': _dashboard_payload(request),
            'user_context': _user_context(request),
        },
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
        items = [_lab_to_dict(item) for item in Lab.objects.select_related("region", "district", "ward", "street").order_by("name")]
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
        items = [_site_to_dict(item) for item in Site.objects.select_related("study", "lab", "region", "district", "ward", "street").order_by("name")]
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
        error = _save_model(site)
        if error:
            return error
        return JsonResponse(_site_to_dict(site), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_reference_site_detail(request, site_id: str):
    try:
        site = Site.objects.get(id=site_id)
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
        error = _save_model(site)
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
    items = []
    if source == "labs":
        queryset = Lab.objects.order_by("name")
        if query:
            queryset = queryset.filter(name__icontains=query)
        items = [_model_to_option(item) for item in queryset[:50]]
    elif source == "studies":
        queryset = Study.objects.order_by("name")
        if query:
            queryset = queryset.filter(name__icontains=query)
        items = [_model_to_option(item) for item in queryset[:50]]
    elif source == "sites":
        queryset = Site.objects.order_by("name")
        if query:
            queryset = queryset.filter(name__icontains=query)
        items = [_model_to_option(item) for item in queryset[:50]]
    elif source == "regions":
        queryset = TanzaniaRegion.objects.order_by("name")
        if query:
            queryset = queryset.filter(name__icontains=query)
        items = [_model_to_option(item) for item in queryset[:50]]
    elif source == "districts":
        queryset = TanzaniaDistrict.objects.order_by("name")
        if request.GET.get("region_id"):
            queryset = queryset.filter(region_id=request.GET["region_id"])
        if query:
            queryset = queryset.filter(name__icontains=query)
        items = [_model_to_option(item) for item in queryset[:50]]
    elif source == "wards":
        queryset = TanzaniaWard.objects.order_by("name")
        if request.GET.get("district_id"):
            queryset = queryset.filter(district_id=request.GET["district_id"])
        if query:
            queryset = queryset.filter(name__icontains=query)
        items = [_model_to_option(item) for item in queryset[:50]]
    elif source == "streets":
        queryset = TanzaniaStreet.objects.order_by("name")
        if request.GET.get("ward_id"):
            queryset = queryset.filter(ward_id=request.GET["ward_id"])
        if query:
            queryset = queryset.filter(name__icontains=query)
        items = [_model_to_option(item) for item in queryset[:50]]
    else:
        return JsonResponse({"error": "unsupported_source"}, status=400)
    return JsonResponse({"source": source, "items": items})


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
def lims_metadata_vocabularies(request):
    if request.method == "GET":
        forbidden = require_lims_permission(request, "lims.metadata.view")
        if forbidden:
            return forbidden
        items = [_vocabulary_to_dict(item) for item in MetadataVocabulary.objects.prefetch_related("items").order_by("name")]
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
        vocabulary = MetadataVocabulary.objects.prefetch_related("items").get(id=vocabulary_id)
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
            for item in MetadataSchema.objects.prefetch_related("versions__fields__field_definition").order_by("name")
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
        return JsonResponse(_schema_to_dict(schema), status=201)
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@csrf_exempt
def lims_metadata_schema_detail(request, schema_id: str):
    try:
        schema = MetadataSchema.objects.prefetch_related("versions__fields__field_definition").get(id=schema_id)
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
        items = [
            _schema_version_to_dict(item)
            for item in schema.versions.prefetch_related("fields__field_definition").order_by("-version_number")
        ]
        return JsonResponse({"items": items})
    if request.method == "POST":
        forbidden = require_lims_permission(request, "lims.metadata.manage")
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "invalid_json"}, status=400)
        fields_payload = payload.get("fields")
        if not isinstance(fields_payload, list) or not fields_payload:
            return JsonResponse({"error": "fields must be a non-empty list"}, status=400)
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
        for index, field_payload in enumerate(fields_payload, start=1):
            if not isinstance(field_payload, dict):
                return JsonResponse({"error": "field must be an object"}, status=400)
            field_definition, error = _resolve_optional_fk(
                MetadataFieldDefinition,
                field_payload.get("field_definition_id"),
                "field_definition_not_found",
            )
            if error:
                return error
            if field_definition is None:
                return JsonResponse({"error": "field_definition_id is required"}, status=400)
            validation_rules = field_payload.get("validation_rules") or {}
            condition = field_payload.get("condition") or {}
            if not isinstance(validation_rules, dict):
                return JsonResponse({"error": "validation_rules must be an object"}, status=400)
            if not isinstance(condition, dict):
                return JsonResponse({"error": "condition must be an object"}, status=400)
            schema_field = MetadataSchemaField(
                schema_version=version,
                field_definition=field_definition,
                field_key=str(field_payload.get("field_key") or field_definition.code).strip(),
                position=int(field_payload.get("position") or index),
                required=bool(field_payload.get("required", False)),
                validation_rules=validation_rules,
                condition=condition,
            )
            error = _save_model(schema_field)
            if error:
                version.delete()
                return error
        version.refresh_from_db()
        return JsonResponse(_schema_version_to_dict(version), status=201)
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
