import logging
import json
import time
from uuid import UUID
from sqlalchemy import select
from app.cache.redis_client import get_redis
from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.jobs.queue import enqueue
from app.models.snippet import Snippet
from app.utils.dep import tokenize

logger = logging.getLogger("app")


async def index_snippet(payload):
    redis = get_redis()
    snippet_id = payload["snippet_id"]
    short_id = payload["short_id"]
    text = payload["text"]

    tokens = tokenize(text)
    pipe = redis.pipeline()
    for token in tokens:
        pipe.sadd(f"search:index:{token}", short_id)
    await pipe.execute()

    logger.info(
        "snippet_indexed", extra={"snippet_id": snippet_id, "short_id": short_id}
    )


async def remove_index(payload):
    redis = get_redis()
    short_id = payload["short_id"]
    text = payload["text"]

    tokens = tokenize(text)
    pipe = redis.pipeline()
    for token in tokens:
        pipe.srem(f"search:index:{token}", short_id)

    async for cache_key in redis.scan_iter(match=f"snippet:{short_id}:v*"):
        pipe.delete(cache_key)

    await pipe.execute()
    logger.info("snippet_index_removed", extra={"short_id": short_id})


async def _resolve_legacy_short_ids(snippet_ids: set[str]) -> dict[str, str]:
    legacy_ids = []
    for snippet_id in snippet_ids:
        try:
            legacy_ids.append(UUID(snippet_id))
        except ValueError:
            logger.warning(
                "invalid_expiry_identifier", extra={"identifier": snippet_id}
            )

    if not legacy_ids:
        return {}

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Snippet.id, Snippet.short_id)
            .where(Snippet.id.in_(legacy_ids))
            .execution_options(include_deleted=True)
        )

    return {str(snippet_id): short_id for snippet_id, short_id in result.all()}


async def cleanup_expired(payload=None):
    redis = get_redis()
    now = int(time.time())
    expired = await redis.zrangebyscore("snippets:expiry", 0, now)

    parsed_keys: list[tuple[str, str | None, str | None]] = []
    legacy_identifiers: set[str] = set()

    for key in expired:
        try:
            _, identifier, version = key.split(":", 2)
        except ValueError:
            logger.warning("invalid_expiry_key", extra={"key": key})
            parsed_keys.append((key, None, None))
            continue
        parsed_keys.append((key, identifier, version))
        if len(identifier) != 8:
            legacy_identifiers.add(identifier)

    legacy_short_ids = await _resolve_legacy_short_ids(legacy_identifiers)

    if parsed_keys:
        pipe = redis.pipeline()
        for key, identifier, version in parsed_keys:
            pipe.zrem("snippets:expiry", key)
            if identifier is None or version is None:
                continue
            short_id = (
                identifier if len(identifier) == 8 else legacy_short_ids.get(identifier)
            )
            if short_id is None:
                continue
            pipe.delete(f"snippet:{short_id}:v{version}")
            pipe.delete(f"snippet:{short_id}:vlatest")
        await pipe.execute()
        logger.info("expired_snippets_cleaned", extra={"count": len(parsed_keys)})

    await enqueue("cleanup_expired", {}, delay=settings.CLEANUP_EXPIRED_DELAY_SECONDS)


async def recover_stuck_jobs(payload=None):
    redis = get_redis()
    jobs = await redis.lrange(settings.PROCESSING, 0, -1)
    stuck_count = 0
    now = time.time()

    for job_data in jobs:
        job = json.loads(job_data)
        if now - job.get("processing_started_at", job["created_at"]) > 300:
            stuck_count += 1
            await redis.lrem(settings.PROCESSING, 1, job_data)
            job["processing_started_at"] = now
            await redis.lpush(settings.QUEUE, json.dumps(job))

    if stuck_count > 0:
        logger.info("stuck_jobs_requeued", extra={"count": stuck_count})

    await enqueue(
        "recover_stuck_jobs", {}, delay=settings.RECOVER_STUCK_JOBS_DELAY_SECONDS
    )


async def flush_views_to_db(payload=None):

    redis = get_redis()

    keys = await redis.keys("snippet:views:*")
    flushed_count = 0

    async with AsyncSessionLocal() as session:
        for key in keys:
            short_id = key.split(":")[-1]
            count = await redis.get(key)
            if count is None:
                continue

            stmt = select(Snippet).where(Snippet.short_id == short_id)
            snippet_obj = (await session.execute(stmt)).scalar_one_or_none()

            if snippet_obj:
                snippet_obj.views += int(count)
                flushed_count += 1

        if flushed_count > 0:
            await session.commit()

    if keys:
        pipe = redis.pipeline()
        for key in keys:
            pipe.delete(key)
        await pipe.execute()

    logger.info(
        "flushed_snippet_views_to_db",
        extra={"flushed_count": flushed_count, "redis_keys": len(keys)}
    )

    await enqueue(
        "flush_views_to_db",
        {},
        delay=settings.FLUSH_VIEWS_INTERVAL_SECONDS
    )

TASKS = {
    "index_snippet": index_snippet,
    "cleanup_expired": cleanup_expired,
    "remove_snippet_index": remove_index,
    "recover_stuck_jobs": recover_stuck_jobs,
    "flush_views_to_db": flush_views_to_db
}
