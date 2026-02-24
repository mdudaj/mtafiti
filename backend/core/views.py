from django.db import connection
from django.db.utils import DatabaseError
from django.http import JsonResponse


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
