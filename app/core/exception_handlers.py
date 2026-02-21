from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError

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
    return JSONResponse(
        status_code=422,
        content=_payload(
            request,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details={"errors": exc.errors()},
        ),
    )

async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=_payload(
            request,
            code="HTTP_ERROR",
            message="HTTP ERROR",
            details=str(exc.detail),
        ),
    )

async def unhandled_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=_payload(
            request,
            code="INTERNAL_SERVER_ERROR",
            message="Something went wrong",
            details=str(exc),
        ),
    )