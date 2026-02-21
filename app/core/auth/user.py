from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from app.models import User
from app.db.database import AsyncSessionLocal
from typing import AsyncGenerator

async def get_user_db() -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    async with AsyncSessionLocal() as session:
        yield SQLAlchemyUserDatabase(session, User)