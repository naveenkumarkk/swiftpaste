from functools import wraps
from fastapi import Request
from app.rate_limiter.rate_limiter import rate_limiter
from app.core.config import settings

def rate_limit(capacity: int | None = None, refill_rate: int | None = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request")
            if request is None:
                raise RuntimeError("Request object required for rate limiting")

            # Determine user_id: prefer authenticated user, else fallback to IP
            user = kwargs.get("user", None)
            user_id = str(user.id) if user else request.client.host

            _capacity = capacity if capacity is not None else settings.CAPACITY
            _refill_rate = refill_rate if refill_rate is not None else settings.REFILL_RATE

            await rate_limiter(
                user_id=user_id,
                capacity=_capacity,
                refill_rate=_refill_rate,
            )

            return await func(*args, **kwargs)

        return wrapper

    return decorator