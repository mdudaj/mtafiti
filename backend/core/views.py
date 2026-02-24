import json
import os
from typing import Any

from django.db import connection
from django.db.utils import DatabaseError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .events import maybe_publish_event
from .models import DataAsset, IngestionRequest


def _tenant_schema(request) -> str:
    tenant = getattr(request, 'tenant', None)
    return tenant.schema_name if tenant else connection.schema_name


def health(request):
    return JsonResponse({'schema': connection.schema_name})


def probe_ok(request):
    return JsonResponse({'status': 'ok'})

def livez(request):
    return probe_ok(request)


def healthz(request):
    return probe_ok(request)


def readyz(request):
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except DatabaseError:
        return JsonResponse({'status': 'not-ready'}, status=503)
    return JsonResponse({'status': 'ok'})


def _asset_to_dict(asset: DataAsset) -> dict[str, Any]:
    return {
        'id': str(asset.id),
        'qualified_name': asset.qualified_name,
        'display_name': asset.display_name,
        'asset_type': asset.asset_type,
        'properties': asset.properties,
        'created_at': asset.created_at.isoformat(),
        'updated_at': asset.updated_at.isoformat(),
    }


def _parse_json_body(request):
    try:
        body = request.body.decode('utf-8') if request.body else ''
        return json.loads(body or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _ingestion_to_dict(ing: IngestionRequest) -> dict[str, Any]:
    return {
        'id': str(ing.id),
        'connector': ing.connector,
        'source': ing.source,
        'mode': ing.mode if ing.mode else None,
        'status': ing.status,
        'created_at': ing.created_at.isoformat(),
        'updated_at': ing.updated_at.isoformat(),
    }


@csrf_exempt
def ingestions(request):
    """Create tenant-scoped ingestion requests."""
    if request.method == 'POST':
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)

        connector = payload.get('connector')
        source = payload.get('source')
        if not connector:
            return JsonResponse({'error': 'connector is required'}, status=400)
        if source is None or not isinstance(source, dict):
            return JsonResponse({'error': 'source must be an object'}, status=400)

        ing = IngestionRequest.objects.create(
            connector=connector,
            source=source,
            mode=payload.get('mode') or '',
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='ingestion.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.ingestion.created',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_ingestion_to_dict(ing),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_ingestion_to_dict(ing), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def ingestion_detail(request, ingestion_id: str):
    try:
        ing = IngestionRequest.objects.get(id=ingestion_id)
    except IngestionRequest.DoesNotExist:
        return JsonResponse({'error': 'not_found'}, status=404)

    if request.method == 'GET':
        return JsonResponse(_ingestion_to_dict(ing))

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def assets(request):
    """List/create tenant-scoped DataAssets.

    GET supports simple offset pagination via ?limit= (default 100, max 500) and ?offset= (default 0).
    """
    if request.method == 'GET':
        try:
            limit = int(request.GET.get('limit', '100'))
            offset = int(request.GET.get('offset', '0'))
        except ValueError:
            return JsonResponse({'error': 'limit/offset must be integers'}, status=400)
        limit = min(max(limit, 1), 500)
        offset = max(offset, 0)

        qs = DataAsset.objects.order_by('created_at')[offset : offset + limit]
        items = [_asset_to_dict(a) for a in qs]
        return JsonResponse({'items': items})

    if request.method == 'POST':
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)

        qualified_name = payload.get('qualified_name')
        asset_type = payload.get('asset_type')
        if not qualified_name or not asset_type:
            return JsonResponse({'error': 'qualified_name and asset_type are required'}, status=400)

        asset = DataAsset.objects.create(
            qualified_name=qualified_name,
            display_name=payload.get('display_name') or qualified_name,
            asset_type=asset_type,
            properties=payload.get('properties') or {},
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='asset.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.catalog.asset.created',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_asset_to_dict(asset),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_asset_to_dict(asset), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def asset_detail(request, asset_id: str):
    try:
        asset = DataAsset.objects.get(id=asset_id)
    except DataAsset.DoesNotExist:
        return JsonResponse({'error': 'not_found'}, status=404)

    if request.method == 'GET':
        return JsonResponse(_asset_to_dict(asset))

    if request.method == 'PUT':
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)

        if 'asset_type' in payload and payload['asset_type'] != asset.asset_type:
            return JsonResponse({'error': 'asset_type is immutable'}, status=400)

        if 'display_name' in payload:
            if payload['display_name'] is None:
                return JsonResponse({'error': 'display_name cannot be null'}, status=400)
            asset.display_name = payload['display_name']
        if 'properties' in payload:
            props = payload['properties']
            if props is None:
                asset.properties = {}
            else:
                if not isinstance(props, dict):
                    return JsonResponse({'error': 'properties must be an object'}, status=400)
                merged = dict(asset.properties)
                for k, v in props.items():
                    if v is None:
                        merged.pop(k, None)
                    else:
                        merged[k] = v
                asset.properties = merged
        asset.save()
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='asset.updated',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.catalog.asset.updated',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_asset_to_dict(asset),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_asset_to_dict(asset))

    return JsonResponse({'error': 'method_not_allowed'}, status=405)
