import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    'edmp_http_requests',
    'Total HTTP requests by method, path, and status.',
    ['method', 'path', 'status'],
)
HTTP_REQUEST_LATENCY_SECONDS = Histogram(
    'edmp_http_request_latency_seconds',
    'HTTP request latency by method and path.',
    ['method', 'path'],
)
HTTP_INFLIGHT_REQUESTS = Gauge(
    'edmp_http_inflight_requests',
    'In-flight HTTP requests by method and path.',
    ['method', 'path'],
)
DB_READINESS_ERRORS = Counter(
    'edmp_db_readiness_errors',
    'Readiness DB connectivity errors.',
)
CELERY_TASK_EXECUTIONS = Counter(
    'edmp_celery_task_executions',
    'Celery task execution count by task and outcome.',
    ['task', 'status'],
)
CELERY_TASK_DURATION_SECONDS = Histogram(
    'edmp_celery_task_duration_seconds',
    'Celery task run duration in seconds by task.',
    ['task'],
)


def metrics_response():
    return generate_latest(), CONTENT_TYPE_LATEST


class MetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        method = request.method
        path = request.path
        start = time.perf_counter()
        gauge = HTTP_INFLIGHT_REQUESTS.labels(method=method, path=path)
        gauge.inc()
        try:
            response = self.get_response(request)
            path = request.resolver_match.route if getattr(request, 'resolver_match', None) else request.path
            HTTP_REQUESTS.labels(method=method, path=path, status=str(response.status_code)).inc()
            HTTP_REQUEST_LATENCY_SECONDS.labels(method=method, path=path).observe(time.perf_counter() - start)
            return response
        except Exception:
            HTTP_REQUESTS.labels(method=method, path=path, status='500').inc()
            HTTP_REQUEST_LATENCY_SECONDS.labels(method=method, path=path).observe(time.perf_counter() - start)
            raise
        finally:
            gauge.dec()
