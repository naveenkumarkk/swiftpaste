import json
import asyncio
import logging

from app.cache.redis_client import get_redis
from app.core.config import settings
from app.core.logging import setup_logging
from app.jobs.tasks import TASKS

logger = logging.getLogger("app")


async def worker():
    redis = get_redis()
    logger.info(
        "worker_started",
        extra={"queue": settings.QUEUE, "processing_queue": settings.PROCESSING},
    )
    while True:
        job_data = await redis.brpoplpush(
            settings.QUEUE,
            settings.PROCESSING,
            timeout=30,
        )

        if job_data is None:
            continue

        try:
            job = json.loads(job_data)
        except Exception:
            await redis.lrem(settings.PROCESSING, 1, job_data)
            logger.exception("invalid_job_payload")
            continue

        try:
            job_type = job["type"]
            payload = job["payload"]

            handler = TASKS[job_type]

            await handler(payload)

            await redis.lrem(settings.PROCESSING, 1, job_data)

        except Exception:
            retries = job.get("retries", 3) - 1
            job["retries"] = retries

            await redis.lrem(settings.PROCESSING, 1, job_data)

            if retries > 0:
                await redis.lpush(settings.QUEUE, json.dumps(job))
            else:
                await redis.lpush(settings.FAILED, json.dumps(job))

            logger.exception("job_failed", extra={"job_id": job.get("id")})


if __name__ == "__main__":
    setup_logging("DEBUG" if settings.DEBUG else "INFO")
    asyncio.run(worker())