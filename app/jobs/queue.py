import json
import uuid
import time
import logging
from app.cache.redis_client import get_redis
from app.core.config import settings

logger = logging.getLogger("app")


async def enqueue(job_type: str, payload: dict, delay: int = 0, retries: int = 3):

    redis = get_redis()
    job = {
        "id": str(uuid.uuid4()),
        "type": job_type,
        "payload": payload,
        "retries": retries,
        "created_at": int(time.time()),
    }

    job_data = json.dumps(job)
    logger.info(
        "Jobs Enqueue is being started",
        extra={"job_type": job_type, "job": job},
    )
    if delay == 0:
        await redis.lpush(settings.QUEUE, job_data)
    else:
        run_at = int(time.time()) + delay
        await redis.zadd("jobs:scheduled", {job_data: run_at})

    return job["id"]
