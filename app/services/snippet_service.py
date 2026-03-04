# app/services/snippet_service.py

from uuid import UUID
from datetime import datetime, timezone
import logging
from app.cache.redis_client import get_redis
from fastapi import status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app.metrics.cache_metrics import cache_hit, cache_error, cache_miss
from app.core.config import settings
from app.core.enum import VisibilityType
from app.core.errors import AppError
from app.models.snippet import Snippet
from app.models.snippet_version import SnippetVersion
from app.schemas.snippet import (
    SnippetCreate,
    SnippetUpdate,
    SnippetOut,
    SnippetOutResponse,
    SnippetResponse,
    SnippetVersionResponse
)
from app.utils.dep import generate_short_id, compute_expires_at
import json
from typing import Any

logger = logging.getLogger("app")


def _cache_key(short_id: str) -> str:
    return f"snippet:{short_id}"


def _serialize_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _deserialize_payload(raw: str) -> dict[str, Any]:
    return json.loads(raw)


async def create_snippet(
    db_session: AsyncSession,
    payload: SnippetCreate,
    user,
    request_id: str | None = None,
) -> SnippetResponse:

    data = payload.model_dump()
    data["author_id"] = user.id

    snippet_version_data = {
        "content": data.pop("content"),
        "visibility": data.pop("visibility"),
        "expires_at": data.pop("expires_at"),
        "version": 1,
    }

    # Retry on rare short_id collisions
    for _ in range(2):
        snippet = Snippet(**data, short_id=generate_short_id(8))
        db_session.add(snippet)

        try:
            # Flush to get snippet.id without committing
            await db_session.flush()

            # Create version and associate with snippet
            snippet_version = SnippetVersion(
                **snippet_version_data,
                snippet_id=snippet.id,
            )
            db_session.add(snippet_version)

            await db_session.commit()

            stmt = (
                select(Snippet)
                .options(
                    selectinload(Snippet.author),
                    selectinload(Snippet.versions)
                )
                .where(Snippet.id == snippet.id)
            )
            snippet = (await db_session.execute(stmt)).scalar_one()

            latest_version_obj = next(
                (v for v in snippet.versions if v.version == snippet.latest_version),
                snippet.versions[0]
            )

            logger.info(
                "snippet_created",
                extra={
                    "request_id": request_id,
                    "snippet_id": str(snippet.id),
                    "short_id": snippet.short_id,
                    "user_id": str(user.id),
                },
            )

            return SnippetResponse(
                id=snippet.id,
                short_id=snippet.short_id,
                created_at=snippet.created_at,
                author=snippet.author,
                latest_version=SnippetVersionResponse(
                    version=latest_version_obj.version,
                    content=latest_version_obj.content,
                    visibility=latest_version_obj.visibility,
                    expires_at=latest_version_obj.expires_at,
                )
            )

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
    user,
    request_id: str | None = None,
) -> Snippet:  # <- was SnippetResponse
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


async def get_snippet_cached(
    short_id: str,
    db_session: AsyncSession,
    user,
    request_id: str | None = None,
) -> SnippetResponse:
    r = get_redis()
    key = _cache_key(short_id)

    # 1) Cache read
    try:
        raw = await r.get(key)
        if raw:
            cache_hit.inc()
            data = _deserialize_payload(raw)  # dict
            # validate dict -> SnippetResponse
            return SnippetResponse.model_validate(data)
        cache_miss.inc()
    except Exception:
        cache_error.inc()

    # 2) DB read (and auth check)
    snippet = await snippet_out_view(short_id, db_session, user, request_id)

    # 3) Build the actual response object from ORM
    resp = SnippetResponse.model_validate(snippet, from_attributes=True)

    # 4) Cache ONLY public (so cached responses are not user-dependent)
    if snippet.visibility == VisibilityType.PUBLIC:
        payload = resp.model_dump(mode="json")  # <- fixes UUID/datetime/enum shape
        try:
            await r.setex(key, settings.CACHE_TTL_SECONDS, _serialize_payload(payload))
        except Exception:
            cache_error.inc()

    return resp
