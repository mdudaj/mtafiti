import json
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django_tenants.utils import schema_context

from .models import Domain, Tenant


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


@csrf_exempt
def tenants(request):
    """Public control-plane API for tenant administration (scaffold)."""
    with schema_context('public'):
        if request.method == 'GET':
            items = [_tenant_to_dict(t) for t in Tenant.objects.order_by('created_on')]
            return JsonResponse({'items': items})

        if request.method == 'POST':
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

            return JsonResponse(_tenant_to_dict(tenant), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)
