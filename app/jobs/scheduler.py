import asyncio
from app.cache.redis_client import get_redis
import time
from app.core.config import settings
from app.jobs.queue import enqueue


async def dispatch_scheduled_jobs():
    redis = await get_redis()

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


async def schedule_maintenance():

    await enqueue("cleanup_expired", {}, retries=3)
    await enqueue("recover_stuck_jobs", {}, retries=3)

    await dispatch_scheduled_jobs()


if __name__ == "__main__":
    asyncio.run(schedule_maintenance())
