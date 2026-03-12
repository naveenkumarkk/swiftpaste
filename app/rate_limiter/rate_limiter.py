from app.core.config import settings
import time
from app.rate_limiter.token_bucket import token_bucket
from app.core.errors import AppError
from fastapi import status

async def rate_limiter(user_id: str, capacity: int = None, refill_rate: int = None):

    now = int(time.time())
   
    capacity = capacity or settings.CAPACITY
    refill_rate = refill_rate or settings.REFILL_RATE

    allowed = await token_bucket(
        keys=[f"rate_limit:{user_id}"],
        args=[capacity, refill_rate, now],
    )

    if allowed == 0:
        raise AppError(
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            message="Rate Limit Exceeded",
        )