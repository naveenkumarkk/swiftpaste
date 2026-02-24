from fastapi_users import schemas
from uuid import UUID
from fastapi_users.manager import UUIDIDMixin
from fastapi_users import BaseUserManager
from app.models.user import User
class UserRead(schemas.BaseUser[UUID]):
    pass

class UserCreate(schemas.BaseUserCreate):
    pass

class UserUpdate(schemas.BaseUserUpdate):
    pass

class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    # UUIDIDMixin provides parse_id() for UUIDs
    pass