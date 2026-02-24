from fastapi_users import BaseUserManager
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from app.models.user import User
from app.db.database import AsyncSessionLocal
from uuid import UUID
from app.core.config import settings
from typing import AsyncGenerator
from fastapi_users.manager import UUIDIDMixin

class UserManager(UUIDIDMixin,BaseUserManager[User, UUID]):
    reset_password_token_secret = settings.RESET_PASSWORD_TOKEN_SECRET
    verification_token_secret = settings.VERIFICATION_TOKEN_SECRET

    async def on_after_register(self, user: User, request=None):
        print(f"User {user.id} has registered.")

async def get_user_manager() -> AsyncGenerator[UserManager, None]:
    async with AsyncSessionLocal() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        yield UserManager(user_db)
