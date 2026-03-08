import time
from starlette.middleware.base import BaseHTTPMiddleware
from app.metrics.request_metrics import (
    request_count,
    request_latency,
    request_errors,
    request_size,
    response_size,
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.perf_counter()
        response = None

        try:
            response = await call_next(request)
            return response
        except Exception:
            request_errors.labels(
                method=request.method, endpoint=request.url.path
            ).inc()
            raise
        finally:
            latency = time.perf_counter() - start_time

            request_latency.labels(
                method=request.method,
                endpoint=request.url.path,
            ).observe(latency)

            request_size.observe(int(request.headers.get("content-length", 0)))

            if response:
                request_count.labels(
                    method=request.method,
                    endpoint=request.url.path,
                    status=response.status_code,
                )
                response_size.observe(len(response.body))
