# app/routes/health.py
from fastapi import APIRouter, Depends, Request, status, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_session
from app.services.health_service import check_database, check_redis
from app.core.errors import AppError
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import logging
import asyncio
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger("app")


async def perform_health_checks(
    db: AsyncSession, request_id: str | None = None
) -> dict:
    try:
        db_healthy = await asyncio.wait_for(
            check_database(db, request_id), timeout=settings.HEALTH_CHECK_TIMEOUT
        )
    except Exception:
        db_healthy = False

    try:
        redis_healthy = await asyncio.wait_for(check_redis(request_id), timeout=0.1)
    except Exception:
        redis_healthy = False

    status_str = "healthy" if db_healthy and redis_healthy else "unhealthy"

    response = {
        "status": status_str,
        "database": "connected" if db_healthy else "disconnected",
        "redis": "connected" if redis_healthy else "disconnected",
        "request_id": request_id,
    }

    logger.info("health_check", extra=response)

    return response


@router.get(
    "/",
    summary="Combined Health Check",
    description="Check the health status of DB and Redis services"
)
async def health_check(request: Request, db: AsyncSession = Depends(get_async_session)):
    request_id = getattr(request.state, "request_id", None)
    response = await perform_health_checks(db, request_id)

    if response["status"] == "unhealthy":
        raise AppError(
            code="HEALTH_CHECK_FAILURE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="One or more services are down",
            details=response,
        )

    return JSONResponse(response)


@router.get("/ready")
async def ready(request: Request, db: AsyncSession = Depends(get_async_session)):
    request_id = getattr(request.state, "request_id", None)
    response = await perform_health_checks(db, request_id)

    if response["status"] == "unhealthy":
        return JSONResponse(
            {
                "status": "unready",
                "database": response["database"],
                "redis": response["redis"],
                "request_id": request_id,
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return JSONResponse(
        {
            "status": "ready",
            "database": response["database"],
            "redis": response["redis"],
            "request_id": request_id,
        }
    )


@router.get("/health", tags=["health"])
async def health():
    return JSONResponse({"status": "ok"})


@router.get("/metrics", tags=["health"])
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
