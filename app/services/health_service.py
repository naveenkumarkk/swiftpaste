from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from sqlalchemy import text
import logging

logger = logging.getLogger("app")


async def check_database(
    db_session: AsyncSession,
    request_id: str | None = None,
) -> bool:
    try:
        await asyncio.wait_for(db_session.execute(text("SELECT 1")), timeout=5.0)
        logger.info(
            "health_check",
            extra={"request_id": request_id},
        )
        return True
    except Exception:
        return False
