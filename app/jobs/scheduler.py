import asyncio
import time

from app.cache.redis_client import get_redis
from app.core.config import settings
from app.core.logging import setup_logging
from app.jobs.queue import enqueue
from app.jobs.worker import worker

async def dispatch_scheduled_jobs():
    redis = get_redis()

    while True:
        now = int(time.time())

        jobs = await redis.zrangebyscore("jobs:scheduled", 0, now)

        if jobs:
            pipe = redis.pipeline()

            for job in jobs:
                pipe.zrem("jobs:scheduled", job)
                pipe.lpush(settings.QUEUE, job)
            await pipe.execute()

        await asyncio.sleep(1)


async def main():
    await enqueue("cleanup_expired", {}, retries=3)
    await enqueue("recover_stuck_jobs", {}, retries=3)

    await asyncio.gather(
        worker(),
        dispatch_scheduled_jobs(),
    )

if __name__ == "__main__":
    setup_logging("DEBUG" if settings.DEBUG else "INFO")
    asyncio.run(main())

