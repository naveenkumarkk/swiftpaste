from fastapi_users.authentication import AuthenticationBackend, BearerTransport
from app.core.auth.jwt import get_jwt_stratergy

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_stratergy,
)
