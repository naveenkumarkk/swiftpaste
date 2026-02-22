import secrets
import string
from datetime import datetime, timezone, timedelta

_BASE62 = string.ascii_letters + string.digits  # a-zA-Z0-9


def generate_short_id(length: int = 8) -> str:
    return "".join(secrets.choice(_BASE62) for _ in range(length))


def compute_expires_at(ttl_seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
