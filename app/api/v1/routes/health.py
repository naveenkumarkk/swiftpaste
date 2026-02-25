from fastapi import APIRouter, Depends, Request, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_async_session
from app.services.health_service import check_database
from app.core.errors import AppError
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter()


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="API to check the health status of the system",
)
async def health_check(request: Request, db: AsyncSession = Depends(get_async_session)):
    request_id = getattr(request.state, "request_id", None)
    db_healthy = await check_database(db, request_id)

    if db_healthy:
        return {"status": "healthy", "database": "connected"}
    else:
        raise AppError(
            code="HEALTH_CHECK_FAILED",
            message="Database is Disconnected!",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

@router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)