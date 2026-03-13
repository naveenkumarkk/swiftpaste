from app.cache.redis_client import get_redis
import logging
from app.utils.dep import tokenize
import time
from app.core.config import settings
import json
from app.jobs.queue import enqueue

logger = logging.getLogger("app")


async def index_snippet(payload):

    redis = await get_redis()

    snippet_id = payload["snippet_id"]
    short_id = payload["short_id"]
    text = payload["text"]

    tokens = tokenize(text)
    pipe = redis.pipeline()

    for token in tokens:
        pipe.sadd(f"search:index:{token}", short_id)

    await pipe.execute() 
    logger.info(
        "snippet_indexed",
        extra={"snippet_id": snippet_id, "short_id": short_id},
    )


async def remove_index(payload):
    redis = await get_redis()
    snippet_id = payload["snippet_id"]
    short_id = payload["short_id"]
    text = payload["text"]

    tokens = tokenize(text)

    pipe = redis.pipeline()

    for token in tokens:
        pipe.srem(f"search:index:{token}", short_id)

    pipe.delete(f"snippet:{snippet_id}")
    pipe.delete(f"snippet:{snippet_id}:vlatest")

    await pipe.execute()

    logger.info(
        "snippet_index_removed",
        extra={"snippet_id": snippet_id, "short_id": short_id},
    )


async def cleanup_expired():

    redis = await get_redis()

    now = int(time.time())

    expired = await redis.zrangebyscore("snippets:expiry", 0, now)

    if not expired:
        return

    pipe = redis.pipeline()

    for key in expired:
        _, snippet_id, version = key.split(":")

        pipe.zrem("snippets:expiry", key)
        pipe.delete(f"snippet:{snippet_id}:v{version}")
        pipe.delete(f"snippet:{snippet_id}:vlatest")

    await pipe.execute()
    await enqueue("cleanup_expired", {}, delay=60)
    logger.info("expired_snippets_cleaned", extra={"count": len(expired)})


async def recover_stuck_jobs():
    redis = await get_redis()

    jobs = await redis.lrange(settings.PROCESSING, 0, -1)

    for job_data in jobs:
        job = json.loads(job_data)

        if time.time() - job["created_at"] > 300:
            await redis.lrem(settings.PROCESSING, 1, job_data)
            await redis.lpush(settings.QUEUE, job_data)
    await enqueue("recover_stuck_jobs", {}, delay=300)


TASKS = {
    "index_snippet": index_snippet,
    "cleanup_expired": cleanup_expired,
    "remove_snippet_index": remove_index,
    "recover_stuck_jobs":recover_stuck_jobs
}
