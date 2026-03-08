from __future__ import annotations

from redis.asyncio import Redis
from redis.asyncio import from_url
from app.core.config import settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis

    if _redis is None:
        redis_url = settings.REDIS_URL
        _redis = from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=0.1,  # 100ms connection timeout
            socket_timeout=0.1,  # 100ms read/write timeout
            max_connections=50,
            health_check_interval=30,
        )
    return _redis
