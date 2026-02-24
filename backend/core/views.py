from django.db import connection
from django.db.utils import DatabaseError
from django.http import JsonResponse


def health(request):
    return JsonResponse({'schema': connection.schema_name})


def livez(request):
    return JsonResponse({'status': 'ok'})


def healthz(request):
    return JsonResponse({'status': 'ok'})


def readyz(request):
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except DatabaseError:
        return JsonResponse({'status': 'not-ready'}, status=503)
    return JsonResponse({'status': 'ok'})
