from django.db import connection
from django.http import JsonResponse


def health(request):
    return JsonResponse({'schema': connection.schema_name})

# Create your views here.
