# app/services/snippet_service.py

from uuid import UUID
from datetime import datetime, timezone
import logging

from fastapi import status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.enum import VisibilityType
from app.core.errors import AppError
from app.models.snippet import Snippet
from app.schemas.snippet import (
    SnippetCreate,
    SnippetUpdate,
    SnippetOut,
    SnippetOutResponse,
    SnippetResponse,
)
from app.utils.dep import generate_short_id, compute_expires_at

logger = logging.getLogger("app")


async def create_snippet(
    db_session: AsyncSession,
    payload: SnippetCreate,
    user,
    request_id: str | None = None,
) -> Snippet:
    data = payload.model_dump()
    data["author_id"] = user.id

    # Retry on rare short_id collisions
    for _ in range(2):
        snippet = Snippet(**data, short_id=generate_short_id(8))
        db_session.add(snippet)
        try:
            await db_session.commit()
            await db_session.refresh(snippet)

            stmt = (
                select(Snippet)
                .options(selectinload(Snippet.author))
                .where(Snippet.id == snippet.id)
            )
            snippet = (await db_session.execute(stmt)).scalar_one()

            logger.info(
                "snippet_created",
                extra={
                    "request_id": request_id,
                    "snippet_id": str(snippet.id),
                    "short_id": snippet.short_id,
                    "user_id": str(user.id),
                },
            )
            return snippet
        except IntegrityError:
            await db_session.rollback()

    raise AppError(
        code="SHORT_ID_GENERATION_FAILED",
        message="Could not generate a unique short_id",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def update_snippet(
    id: UUID,
    db_session: AsyncSession,
    payload: SnippetUpdate,
    user,
    request_id: str | None = None,
) -> Snippet:
    stmt = (
        select(Snippet)
        .options(selectinload(Snippet.author))
        .where(Snippet.id == id, Snippet.author_id == user.id)
    )
    snippet = (await db_session.execute(stmt)).scalar_one_or_none()

    if snippet is None:
        raise AppError(
            code="SNIPPET_NOT_FOUND",
            message="Snippet not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(snippet, key, value)

    await db_session.commit()
    await db_session.refresh(snippet)

    logger.info(
        "snippet_updated",
        extra={
            "request_id": request_id,
            "snippet_id": str(id),
            "user_id": str(user.id),
        },
    )
    return snippet


async def delete_snippet(
    id: UUID,
    db_session: AsyncSession,
    user,
    request_id: str | None = None,
) -> None:
    stmt = select(Snippet).where(Snippet.id == id, Snippet.author_id == user.id)
    snippet = (await db_session.execute(stmt)).scalar_one_or_none()

    if snippet is None:
        raise AppError(
            code="SNIPPET_NOT_FOUND",
            message="Snippet not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Triggers ORM-level soft delete hook (before_flush)
    await db_session.delete(snippet)
    await db_session.commit()

    logger.info(
        "snippet_deleted",
        extra={
            "request_id": request_id,
            "snippet_id": str(id),
            "user_id": str(user.id),
        },
    )
    return None


async def snippet_out_url(
    id: UUID,
    db_session: AsyncSession,
    payload: SnippetOut,
    user,
    request_id: str | None = None,
) -> SnippetOutResponse:
    stmt = select(Snippet).where(Snippet.id == id, Snippet.author_id == user.id)
    snippet = (await db_session.execute(stmt)).scalar_one_or_none()

    if snippet is None:
        raise AppError(
            code="SNIPPET_NOT_FOUND",
            message="Snippet not found or you don't have access",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    ttl = (
        payload.ttl_seconds
        if payload.ttl_seconds is not None
        else settings.DEFAULT_SHARE_TTL_SECONDS
    )
    snippet.expires_at = compute_expires_at(ttl)

    await db_session.commit()
    await db_session.refresh(snippet)

    logger.info(
        "snippet_share_link_generated",
        extra={
            "request_id": request_id,
            "snippet_id": str(id),
            "short_id": snippet.short_id,
            "user_id": str(user.id),
        },
    )

    return SnippetOutResponse(
        share_url=f"{settings.FRONTEND_BASE_URL}/view/{snippet.short_id}",
        expires_at=snippet.expires_at,
    )


async def snippet_out_view(
    short_id: str,
    db_session: AsyncSession,
    user,  # optional user allowed
    request_id: str | None = None,
) -> SnippetResponse:
    now = datetime.now(timezone.utc)

    stmt = (
        select(Snippet)
        .options(selectinload(Snippet.author))
        .where(
            Snippet.short_id == short_id,
            or_(Snippet.expires_at.is_(None), Snippet.expires_at > now),
        )
    )

    snippet = (await db_session.execute(stmt)).scalar_one_or_none()

    if snippet is None:
        raise AppError(
            code="SNIPPET_NOT_FOUND",
            message="Snippet not found",
            details="Snippet may be expired. Ask the author to share again.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # If private, require login
    if snippet.visibility == VisibilityType.PRIVATE and user is None:
        raise AppError(
            code="SNIPPET_ACCESS_RESTRICTION",
            message="Snippet is private",
            details="Login to access it.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    logger.info(
        "snippet_share_link_view",
        extra={
            "request_id": request_id,
            "snippet_id": str(snippet.id),
            "short_id": snippet.short_id,
        },
    )
    return snippet
