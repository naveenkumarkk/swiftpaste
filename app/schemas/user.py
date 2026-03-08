from fastapi_users import schemas
from uuid import UUID
from fastapi_users.manager import UUIDIDMixin
from fastapi_users import BaseUserManager
from app.models.user import User
from pydantic import BaseModel, EmailStr, ConfigDict


class UserRead(schemas.BaseUser[UUID]):
    id: UUID
    email: EmailStr
    username: str


class UserCreate(schemas.BaseUserCreate):
    email: EmailStr
    password: str
    username: str


class UserUpdate(schemas.BaseUserUpdate):
    username: str | None = None


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    # UUIDIDMixin provides parse_id() for UUIDs
    pass


class UserMeta(BaseModel):
    id: UUID
    email: EmailStr
    username: str

    model_config = ConfigDict(from_attributes=True)


class UserCreateCustom(BaseModel):
    email: EmailStr
    password: str
    username: str
