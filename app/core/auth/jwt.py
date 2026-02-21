from fastapi_users.authentication import JWTStrategy
from  app.core.config import settings

def get_jwt_stratergy()-> JWTStrategy:
    return JWTStrategy(
        secret=settings.JWT_SECRET,
        lifetime_seconds=settings.JWT_LIFETIME_SECONDS
    )