import asyncio
import time
from app.cache.redis_client import get_redis
from app.core.config import settings
from app.core.logging import setup_logging
from app.jobs.queue import enqueue
from app.jobs.worker import worker

SCHEDULED_LOCK_PREFIX = "lock:scheduled_job:" 

async def dispatch_scheduled_jobs():
    redis = get_redis()

    while True:
        now = int(time.time())
        jobs = await redis.zrangebyscore("jobs:scheduled", 0, now)

        if jobs:
            pipe = redis.pipeline()
            for job_data in jobs:
                pipe.zrem("jobs:scheduled", job_data)
                pipe.lpush(settings.QUEUE, job_data)
            await pipe.execute()

        await asyncio.sleep(3)


async def enqueue_initial_job(job_type: str, payload=None, retries=3):
    redis = get_redis()
    payload = payload or {}

    queue_jobs = await redis.lrange(settings.QUEUE, 0, -1)
    scheduled_jobs = await redis.zrange("jobs:scheduled", 0, -1)

    all_jobs = queue_jobs + scheduled_jobs

    if any(job_type in job for job in all_jobs):
        return  

    await enqueue(job_type, payload, retries=retries)


async def main():
    await enqueue_initial_job("cleanup_expired")
    await enqueue_initial_job("recover_stuck_jobs")
    await enqueue_initial_job("flush_views_to_db")

    await asyncio.gather(
        worker(),
        dispatch_scheduled_jobs(),
    )


if __name__ == "__main__":
    setup_logging("DEBUG" if settings.DEBUG else "INFO")
    asyncio.run(main())