import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from core.identity import request_roles

from .permissions import permission_summary_for_roles, require_lims_permission
from .models import (
    Lab,
    Site,
    Study,
    TanzaniaAddressSyncRun,
    TanzaniaDistrict,
    TanzaniaRegion,
    TanzaniaStreet,
    TanzaniaWard,
)
from .services import sync_run_to_dict
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
