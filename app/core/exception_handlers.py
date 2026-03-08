from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import DBAPIError
import logging

from app.core.errors import AppError

logger = logging.getLogger("app")


def _payload(request: Request, code: str, message: str, details=None):
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "requestId": getattr(request.state, "request_id", None),
        }
    }


async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content=_payload(request, exc.code, exc.message, exc.details),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.error("validation_error", extra={"errors": exc.errors()})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=_payload(
            request,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details="Validation error. Contact admin.",
        ),
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException):
    logger.exception("http_error")

    return JSONResponse(
        status_code=exc.status_code,
        content=_payload(
            request,
            code="HTTP_ERROR",
            message="HTTP error",
            details="HTTP error occurred",
        ),
    )


async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_payload(
            request,
            code="INTERNAL_SERVER_ERROR",
            message="Something went wrong",
            details="Check with admin",
        ),
    )


async def db_exception_handler(request: Request, exc: DBAPIError):
    logger.exception("database_failure")

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=_payload(
            request,
            code="DB_QUERY_TIMEOUT",
            message="Database timeout",
            details="Database operation failed",
        ),
    )
