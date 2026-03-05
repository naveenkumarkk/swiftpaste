# app/services/snippet_service.py

from uuid import UUID
from datetime import datetime, timezone
import logging
from app.cache.redis_client import get_redis
from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager, joinedload
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
    SnippetVersionResponse,
)
from app.utils.dep import generate_short_id, compute_expires_at
import json
from typing import Any

logger = logging.getLogger("app")


def _cache_key(short_id: str, version: int | None = None) -> str:
    version_str = str(version) if version is not None else "latest"
    return f"snippet:{short_id}:v{version_str}"


def _serialize_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _deserialize_payload(raw: bytes | str) -> dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


async def create_new_version(
    snippet_id: UUID, content: str, visibility: VisibilityType, db_session: AsyncSession
):
    async with db_session.begin():
        stmt = (
            update(Snippet)
            .where(Snippet.id == snippet_id)
            .values(version_counter=Snippet.version_counter + 1)
            .returning(Snippet.version_counter)
        )

        result = await db_session.execute(stmt)

        next_version = result.scalar_one()

        snippet_version = SnippetVersion(
            snippet_id=snippet_id,
            version=next_version,
            content=content,
            visibility=visibility,
        )

        db_session.add(snippet_version)

    return snippet_version


async def create_snippet(
    db_session: AsyncSession,
    payload: SnippetCreate,
    user,
    request_id: str | None = None,
) -> SnippetResponse:

    data = payload.model_dump()

    snippet_data = {
        "author_id": user.id,
        "title": data.get("title"),
    }

    version_data = {
        "content": data["content"],
        "visibility": data["visibility"],
    }

    for _ in range(2):
        snippet = Snippet(**snippet_data, short_id=generate_short_id(8))
        db_session.add(snippet)

        try:
            await db_session.flush()

            snippet_version = SnippetVersion(
                snippet_id=snippet.id,
                version=1,
                **version_data,
            )

            db_session.add(snippet_version)

            await db_session.commit()

            await db_session.refresh(snippet)

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
                title=snippet.title,
                created_at=snippet.created_at,
                author=snippet.author,
                visibility=snippet_version.visibility,
                expires_at=snippet_version.expires_at,
                current_version=SnippetVersionResponse(
                    version=snippet_version.version,
                    content=snippet_version.content,
                ),
            )

        except IntegrityError:
            await db_session.rollback()

    raise AppError(
        code="SHORT_ID_GENERATION_FAILED",
        message="Could not generate a unique short_id",
        status_code=500,
    )


async def update_snippet(
    id: UUID,
    db_session: AsyncSession,
    payload: SnippetUpdate,
    user,
    request_id: str | None = None,
) -> SnippetResponse:

    stmt = (
        select(Snippet)
        .options(joinedload(Snippet.author))
        .where(Snippet.id == id, Snippet.author_id == user.id)
    )
    snippet = (await db_session.execute(stmt)).scalar_one_or_none()
    if snippet is None:
        raise AppError(
            code="SNIPPET_NOT_FOUND",
            message="Snippet not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    data = payload.model_dump(exclude_unset=True)
    if "title" in data:
        snippet.title = data["title"]

    snippet_version = None
    if "content" in data or "visibility" in data:
        snippet_version = await create_new_version(
            id,
            data.get("content"),
            data.get("visibility"),
            db_session=db_session,
        )

    await db_session.commit()
    await db_session.refresh(snippet)

    if snippet_version is None:
        stmt = select(SnippetVersion).where(
            SnippetVersion.snippet_id == snippet.id,
            SnippetVersion.version == snippet.version_counter,
        )
        snippet_version = (await db_session.execute(stmt)).scalar_one()

    try:
        r = get_redis()
        key = _cache_key(snippet.short_id, version=None)
        resp = SnippetResponse(
            id=snippet.id,
            title=snippet.title,
            short_id=snippet.short_id,
            created_at=snippet.created_at,
            latest_version=snippet.version_counter,
            author=snippet.author,
            current_version=SnippetVersionResponse(
                version=snippet_version.version,
                content=snippet_version.content,
                visibility=snippet_version.visibility,
                expires_at=snippet_version.expires_at,
            ),
        )
        payload_json = resp.model_dump(mode="json")
        await r.setex(key, settings.CACHE_TTL_SECONDS, _serialize_payload(payload_json))
    except Exception:
        cache_error.inc()

    logger.info(
        "snippet_updated",
        extra={
            "request_id": request_id,
            "snippet_id": str(id),
            "user_id": str(user.id),
        },
    )

    return resp


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
    version: int | None,
    db_session: AsyncSession,
    payload: SnippetOut,
    user,
    request_id: str | None = None,
) -> SnippetOutResponse:

    snippet_stmt = select(Snippet).where(Snippet.id == id, Snippet.author_id == user.id)
    snippet = (await db_session.execute(snippet_stmt)).scalar_one_or_none()

    if snippet is None:
        raise AppError(
            code="SNIPPET_NOT_FOUND",
            message="Snippet not found or you don't have access",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    version = version or snippet.version_counter

    stmt = (
        select(SnippetVersion)
        .options(joinedload(SnippetVersion.snippet))
        .where(SnippetVersion.snippet_id == id, SnippetVersion.version == version)
    )
    version_obj = (await db_session.execute(stmt)).scalar_one_or_none()

    if version_obj is None:
        raise AppError(
            code="SNIPPET_NOT_FOUND",
            message="Requested snippet version not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    ttl = payload.ttl_seconds or settings.DEFAULT_SHARE_TTL_SECONDS
    version_obj.expires_at = compute_expires_at(ttl)

    await db_session.commit()

    logger.info(
        "snippet_share_link_generated",
        extra={
            "request_id": request_id,
            "snippet_id": str(id),
            "short_id": version_obj.snippet.short_id,
            "user_id": str(user.id),
        },
    )

    return SnippetOutResponse(
        share_url=f"{settings.FRONTEND_BASE_URL}/view/{version_obj.snippet.short_id}?v={version}",
        expires_at=version_obj.expires_at,
    )


async def snippet_out_view(
    short_id: str,
    version: int | None,
    db_session: AsyncSession,
    user,
    request_id: str | None = None,
) -> SnippetResponse:

    now = datetime.now(timezone.utc)

    stmt = (
        select(Snippet)
        .join(Snippet.versions)
        .options(
            joinedload(Snippet.author),
            contains_eager(Snippet.versions),
        )
        .where(Snippet.short_id == short_id)
        .where(
            SnippetVersion.version == version
            if version is not None
            else SnippetVersion.version == Snippet.version_counter
        )
    )

    snippet = (await db_session.execute(stmt)).scalar_one_or_none()

    if snippet is None or not snippet.versions:
        raise AppError(
            code="SNIPPET_NOT_FOUND",
            message="Snippet or requested version not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    version_obj = snippet.versions[0]

    if version_obj.visibility == VisibilityType.PRIVATE and user is None:
        raise AppError(
            code="SNIPPET_ACCESS_RESTRICTION",
            message="Snippet is private",
            details="Login to access it.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if (
        version_obj.expires_at is not None
        and version_obj.expires_at < now
        and (user is None or snippet.author_id != user.id)
    ):
        raise AppError(
            code="SNIPPET_EXPIRED",
            message="Snippet has expired",
            details="Check with the author to extend it!",
            status_code=status.HTTP_423_LOCKED,
        )

    logger.info(
        "snippet_share_link_view",
        extra={
            "request_id": request_id,
            "snippet_id": str(snippet.id),
            "short_id": snippet.short_id,
        },
    )

    return SnippetResponse(
        id=snippet.id,
        title=snippet.title,
        short_id=snippet.short_id,
        created_at=snippet.created_at,
        latest_version=snippet.version_counter,
        author=snippet.author,
        current_version=SnippetVersionResponse(
            version=version_obj.version,
            content=version_obj.content,
            visibility=version_obj.visibility,
            expires_at=version_obj.expires_at,
        ),
    )


async def get_snippet_cached(
    short_id: str,
    version: int | None,
    db_session: AsyncSession,
    user,
    request_id: str | None = None,
) -> SnippetResponse:

    r = get_redis()
    key = _cache_key(short_id, version)

    try:
        raw = await r.get(key)
        if raw:
            cache_hit.inc()
            data = _deserialize_payload(raw)
            return SnippetResponse.model_validate(data)
        cache_miss.inc()
    except Exception:
        cache_error.inc()

    snippet = await snippet_out_view(short_id, version, db_session, user, request_id)

    if snippet.current_version.visibility == VisibilityType.PUBLIC:
        payload = snippet.model_dump(mode="json")
        try:
            await r.setex(key, settings.CACHE_TTL_SECONDS, _serialize_payload(payload))
        except Exception:
            cache_error.inc()

    return snippet
