import json
import os
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django_tenants.utils import schema_context

from core.events import maybe_publish_audit_event, maybe_publish_event
from core.identity import require_role
from .models import (
    Domain,
    Tenant,
    TenantServiceRoute,
    build_service_tenant_domain,
    normalize_subdomain_label,
)


def _parse_json_body(request):
    try:
        body = request.body.decode('utf-8') if request.body else ''
        return json.loads(body or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _tenant_to_dict(tenant: Tenant) -> dict:
    return {
        'id': tenant.id,
        'schema_name': tenant.schema_name,
        'name': tenant.name,
        'created_on': tenant.created_on.isoformat(),
        'domains': [d.domain for d in tenant.domains.order_by('id')],
    }


def _service_route_to_dict(route: TenantServiceRoute) -> dict:
    return {
        'id': route.id,
        'tenant_id': route.tenant_id,
        'service_key': route.service_key,
        'tenant_slug': route.tenant_slug,
        'base_domain': route.base_domain,
        'domain': route.domain,
        'workspace_path': route.workspace_path or None,
        'is_enabled': route.is_enabled,
    }


@csrf_exempt
def tenants(request):
    """Public control-plane API for tenant administration (scaffold)."""
    with schema_context('public'):
        if request.method == 'GET':
            forbidden = require_role(request, 'tenant.admin')
            if forbidden:
                return forbidden
            items = [_tenant_to_dict(t) for t in Tenant.objects.order_by('created_on')]
            return JsonResponse({'items': items})

        if request.method == 'POST':
            forbidden = require_role(request, 'tenant.admin')
            if forbidden:
                return forbidden
            payload = _parse_json_body(request)
            if payload is None:
                return JsonResponse({'error': 'invalid_json'}, status=400)

            name = payload.get('name')
            domain = payload.get('domain')
            schema_name = payload.get('schema_name') or f"t_{uuid.uuid4().hex[:8]}"
            if not name or not domain:
                return JsonResponse({'error': 'name and domain are required'}, status=400)

            try:
                tenant = Tenant(schema_name=schema_name, name=name)
                tenant.full_clean()
                tenant.save()
                dom = Domain(domain=domain, tenant=tenant, is_primary=True)
                dom.full_clean()
                dom.save()
            except ValidationError:
                return JsonResponse({'error': 'validation_error'}, status=400)
            except IntegrityError:
                return JsonResponse({'error': 'conflict'}, status=409)

            maybe_publish_event(
                event_type='tenant.created',
                tenant_id=tenant.schema_name,
                routing_key=f'{tenant.schema_name}.control.tenant.created',
                correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
                user_id=request.headers.get('X-User-Id'),
                data=_tenant_to_dict(tenant),
                rabbitmq_url=os.environ.get('RABBITMQ_URL'),
            )
            maybe_publish_audit_event(
                tenant_id=tenant.schema_name,
                action='tenant.created',
                resource_type='tenant',
                resource_id=str(tenant.id),
                correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
                user_id=request.headers.get('X-User-Id'),
                data=_tenant_to_dict(tenant),
                rabbitmq_url=os.environ.get('RABBITMQ_URL'),
            )
            return JsonResponse(_tenant_to_dict(tenant), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def tenant_services(request):
    with schema_context('public'):
        if request.method == 'GET':
            forbidden = require_role(request, 'tenant.admin')
            if forbidden:
                return forbidden
            tenant_id = request.GET.get('tenant_id')
            qs = TenantServiceRoute.objects.select_related('tenant').order_by('id')
            if tenant_id:
                qs = qs.filter(tenant_id=tenant_id)
            return JsonResponse({'items': [_service_route_to_dict(item) for item in qs]})

        if request.method == 'POST':
            forbidden = require_role(request, 'tenant.admin')
            if forbidden:
                return forbidden
            payload = _parse_json_body(request)
            if payload is None:
                return JsonResponse({'error': 'invalid_json'}, status=400)
            tenant_id = payload.get('tenant_id')
            service_key = normalize_subdomain_label(payload.get('service_key') or '')
            tenant_slug = normalize_subdomain_label(payload.get('tenant_slug') or '')
            base_domain = payload.get('base_domain')
            if not tenant_id or not service_key or not tenant_slug or not base_domain:
                return JsonResponse(
                    {
                        'error': 'tenant_id, service_key, tenant_slug, and base_domain are required'
                    },
                    status=400,
                )
            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except (ValidationError, Tenant.DoesNotExist):
                return JsonResponse({'error': 'tenant_not_found'}, status=404)
            try:
                route = TenantServiceRoute(
                    tenant=tenant,
                    service_key=service_key,
                    tenant_slug=tenant_slug,
                    base_domain=base_domain,
                    domain=build_service_tenant_domain(
                        service_key, tenant_slug, base_domain
                    ),
                    workspace_path=(payload.get('workspace_path') or '').strip(),
                    is_enabled=bool(payload.get('is_enabled', True)),
                )
                route.full_clean()
                route.save()
            except ValidationError:
                return JsonResponse({'error': 'validation_error'}, status=400)
            except IntegrityError:
                return JsonResponse({'error': 'conflict'}, status=409)
            return JsonResponse(_service_route_to_dict(route), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)
