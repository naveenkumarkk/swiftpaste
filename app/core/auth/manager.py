from fastapi_users import FastAPIUsers
from app.core.auth.backend import auth_backend
from app.core.auth.oauth.user_manager import get_user_manager
from app.models.user import User
from uuid import UUID

fastapi_users = FastAPIUsers[User, UUID](
    get_user_manager,
    [auth_backend],
)