import json
import os
import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Q
from django.db.utils import DatabaseError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .events import maybe_publish_audit_event, maybe_publish_event
from .identity import require_any_role, require_role
from .metrics import DB_READINESS_ERRORS, metrics_response
from .models import DataAsset, IngestionRequest, LineageEdge


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
        DB_READINESS_ERRORS.inc()
        return JsonResponse({'status': 'not-ready'}, status=503)
    return JsonResponse({'status': 'ok'})


def metrics(request):
    body, content_type = metrics_response()
    return HttpResponse(body, content_type=content_type)


def _asset_to_dict(asset: DataAsset) -> dict[str, Any]:
    return {
        'id': str(asset.id),
        'qualified_name': asset.qualified_name,
        'display_name': asset.display_name,
        'asset_type': asset.asset_type,
        'description': None if asset.description == '' else asset.description,
        'owner': None if asset.owner == '' else asset.owner,
        'tags': asset.tags,
        'classifications': asset.classifications,
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


def _parse_string_list(value: Any) -> list[str] | None:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    return value


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


def _edge_to_dict(edge: LineageEdge) -> dict[str, Any]:
    return {
        'id': str(edge.id),
        'from_asset_id': str(edge.from_asset_id),
        'to_asset_id': str(edge.to_asset_id),
        'edge_type': edge.edge_type,
        'properties': edge.properties,
        'created_at': edge.created_at.isoformat(),
        'updated_at': edge.updated_at.isoformat(),
    }


def _parse_int_clamped(value: str | None, *, default: int, min_value: int, max_value: int) -> int | None:
    if value is None or value == '':
        return default
    try:
        parsed = int(value)
    except ValueError:
        return None
    return min(max(parsed, min_value), max_value)


@csrf_exempt
def search_assets(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
    if forbidden:
        return forbidden

    query = (request.GET.get('q') or '').strip()
    if not query:
        return JsonResponse({'error': 'q is required'}, status=400)

    try:
        limit = int(request.GET.get('limit', '100'))
        offset = int(request.GET.get('offset', '0'))
    except ValueError:
        return JsonResponse({'error': 'limit/offset must be integers'}, status=400)
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)

    query_lower = query.lower()
    qs = DataAsset.objects.filter(
        Q(display_name__icontains=query)
        | Q(qualified_name__icontains=query)
        | Q(description__icontains=query)
        | Q(asset_type__iexact=query)
        | Q(owner__iexact=query)
        | Q(tags__contains=[query])
        | Q(tags__contains=[query_lower])
        | Q(classifications__contains=[query])
        | Q(classifications__contains=[query_lower])
    ).order_by('-updated_at', 'id')

    count = qs.count()
    results = [_asset_to_dict(a) for a in qs[offset : offset + limit]]
    return JsonResponse({'count': count, 'results': results})


@csrf_exempt
def ingestions(request):
    """Create tenant-scoped ingestion requests."""
    if request.method == 'POST':
        forbidden = require_role(request, 'catalog.editor')
        if forbidden:
            return forbidden
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
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='ingestion.created',
            resource_type='ingestion',
            resource_id=str(ing.id),
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
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        return JsonResponse(_ingestion_to_dict(ing))

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def assets(request):
    """List/create tenant-scoped DataAssets.

    GET supports simple offset pagination via ?limit= (default 100, max 500) and ?offset= (default 0).
    """
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
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
        forbidden = require_role(request, 'catalog.editor')
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)

        qualified_name = payload.get('qualified_name')
        asset_type = payload.get('asset_type')
        description = payload.get('description')
        owner = payload.get('owner')
        if not qualified_name or not asset_type:
            return JsonResponse({'error': 'qualified_name and asset_type are required'}, status=400)
        if description is not None and not isinstance(description, str):
            return JsonResponse({'error': 'description must be a string'}, status=400)
        if owner is not None and not isinstance(owner, str):
            return JsonResponse({'error': 'owner must be a string'}, status=400)
        tags = _parse_string_list(payload.get('tags'))
        if tags is None:
            return JsonResponse({'error': 'tags must be an array of strings'}, status=400)
        classifications = _parse_string_list(payload.get('classifications'))
        if classifications is None:
            return JsonResponse({'error': 'classifications must be an array of strings'}, status=400)

        asset = DataAsset.objects.create(
            qualified_name=qualified_name,
            display_name=payload.get('display_name') or qualified_name,
            asset_type=asset_type,
            description='' if description is None else description,
            owner='' if owner is None else owner,
            tags=tags,
            classifications=classifications,
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
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='asset.created',
            resource_type='asset',
            resource_id=str(asset.id),
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
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        return JsonResponse(_asset_to_dict(asset))

    if request.method == 'PUT':
        forbidden = require_role(request, 'catalog.editor')
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)

        if 'asset_type' in payload and payload['asset_type'] != asset.asset_type:
            return JsonResponse({'error': 'asset_type is immutable'}, status=400)

        if 'display_name' in payload:
            if payload['display_name'] is None:
                return JsonResponse({'error': 'display_name cannot be null'}, status=400)
            asset.display_name = payload['display_name']
        if 'description' in payload:
            if payload['description'] is not None and not isinstance(payload['description'], str):
                return JsonResponse({'error': 'description must be a string'}, status=400)
            asset.description = '' if payload['description'] is None else payload['description']
        if 'owner' in payload:
            if payload['owner'] is not None and not isinstance(payload['owner'], str):
                return JsonResponse({'error': 'owner must be a string'}, status=400)
            asset.owner = '' if payload['owner'] is None else payload['owner']
        if 'tags' in payload:
            tags = _parse_string_list(payload['tags'])
            if tags is None:
                return JsonResponse({'error': 'tags must be an array of strings'}, status=400)
            asset.tags = tags
        if 'classifications' in payload:
            classifications = _parse_string_list(payload['classifications'])
            if classifications is None:
                return JsonResponse({'error': 'classifications must be an array of strings'}, status=400)
            asset.classifications = classifications
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
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='asset.updated',
            resource_type='asset',
            resource_id=str(asset.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_asset_to_dict(asset),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_asset_to_dict(asset))

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def lineage_edges(request):
    """Tenant-scoped lineage edge upsert/query."""
    if request.method == 'POST':
        forbidden = require_role(request, 'catalog.editor')
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        items = payload.get('items')
        if not isinstance(items, list):
            return JsonResponse({'error': 'items must be a list'}, status=400)

        required_ids: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                return JsonResponse({'error': 'items must be objects'}, status=400)
            from_id = item.get('from_asset_id')
            to_id = item.get('to_asset_id')
            edge_type = item.get('edge_type')
            if not from_id or not to_id or not edge_type:
                return JsonResponse({'error': 'from_asset_id, to_asset_id, and edge_type are required'}, status=400)
            try:
                uuid.UUID(from_id)
                uuid.UUID(to_id)
            except ValueError:
                return JsonResponse({'error': 'from_asset_id and to_asset_id must be UUIDs'}, status=400)
            required_ids.add(from_id)
            required_ids.add(to_id)

        existing = {str(a.id) for a in DataAsset.objects.filter(id__in=list(required_ids))}
        if required_ids - existing:
            return JsonResponse({'error': 'asset_not_found'}, status=404)

        out: list[dict[str, Any]] = []
        for item in items:
            edge, _ = LineageEdge.objects.update_or_create(
                from_asset_id=item['from_asset_id'],
                to_asset_id=item['to_asset_id'],
                edge_type=item['edge_type'],
                defaults={'properties': item.get('properties') or {}},
            )
            out.append(_edge_to_dict(edge))

        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='lineage.edge.upserted',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.lineage.edge.upserted',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data={'items': out},
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='lineage.edge.upserted',
            resource_type='lineage_edge',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data={'items': out},
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse({'items': out})

    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        asset_id = request.GET.get('asset_id')
        if not asset_id:
            return JsonResponse({'error': 'asset_id is required'}, status=400)
        try:
            uuid.UUID(asset_id)
        except ValueError:
            return JsonResponse({'error': 'asset_id must be a UUID'}, status=400)
        try:
            DataAsset.objects.get(id=asset_id)
        except (ValidationError, DataAsset.DoesNotExist):
            return JsonResponse({'error': 'not_found'}, status=404)

        direction = request.GET.get('direction', 'downstream')
        if direction not in {'upstream', 'downstream'}:
            return JsonResponse({'error': 'direction must be upstream or downstream'}, status=400)

        depth = _parse_int_clamped(request.GET.get('depth'), default=1, min_value=1, max_value=5)
        if depth is None:
            return JsonResponse({'error': 'depth must be an integer'}, status=400)

        current = {asset_id}
        visited_assets = {asset_id}
        edges: dict[str, LineageEdge] = {}
        for _ in range(depth):
            if not current:
                break
            if direction == 'upstream':
                qs = LineageEdge.objects.filter(to_asset_id__in=list(current))
                next_assets = {str(e.from_asset_id) for e in qs}
            else:
                qs = LineageEdge.objects.filter(from_asset_id__in=list(current))
                next_assets = {str(e.to_asset_id) for e in qs}
            for e in qs:
                edges[str(e.id)] = e
            current = next_assets - visited_assets
            visited_assets |= current

        edge_items = [_edge_to_dict(e) for e in edges.values()]
        assets = [_asset_to_dict(a) for a in DataAsset.objects.filter(id__in=list(visited_assets))]
        return JsonResponse({'edges': edge_items, 'assets': assets})

    return JsonResponse({'error': 'method_not_allowed'}, status=405)
