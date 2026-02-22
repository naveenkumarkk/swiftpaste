import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.config import settings

logger = logging.getLogger("app")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(settings.REQUEST_ID_HEADER) or str(
            uuid.uuid4()
        )
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "unhandled_exception",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                },
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
        response.headers[settings.REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
