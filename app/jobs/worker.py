import json
import asyncio
from app.cache.redis_client import get_redis
from app.jobs.tasks import TASKS
import logging

QUEUE = "jobs"
PROCESSING = "processing"
FAILED = "failed"


logger = logging.getLogger("app")


async def worker():
    redis = await get_redis()
    while True:
        job_data = await redis.brpoplpush(QUEUE, PROCESSING)

        try:
            job = json.loads(job_data)
        except Exception:
            await redis.lrem(PROCESSING, 1, job_data)
            logger.exception("invalid_job_payload")
            continue

        try:
            job_type = job["type"]
            payload = job["payload"]

            handler = TASKS[job_type]

            await handler(payload)

            await redis.lrem(PROCESSING, 1, job_data)
        except Exception as e:
            job["retries"] -= 1
            await redis.lrem(PROCESSING, 1, job_data)

            if job["retries"] > 0:
                await redis.lpush(QUEUE, json.dumps(job))
            else:
                await redis.lpush(FAILED, json.dumps(job))
            logger.exception("job_failed", extra={"job_id": job["id"], "details": e})


if __name__ == "__main__":
    asyncio.run(worker())
