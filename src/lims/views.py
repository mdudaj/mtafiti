from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from core.identity import require_any_role


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


@csrf_exempt
def lims_dashboard_summary(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden
    return JsonResponse(_dashboard_payload(request))


@csrf_exempt
def lims_dashboard_page(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
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
