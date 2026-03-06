from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from app.core.enum import VisibilityType
from datetime import datetime
from app.schemas.user import UserMeta


class SnippetCreate(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    content: str = Field(min_length=1, max_length=50000)
    visibility: VisibilityType = VisibilityType.PUBLIC
    expires_at: Optional[datetime] = None
    author_id: Optional[UUID] = None


class SnippetUpdate(BaseModel):
    title: Optional[str] = Field(min_length=1, max_length=1000)
    content: Optional[str] = Field(min_length=1, max_length=50000)


class SnippetVersionResponse(BaseModel):
    version: int
    content: str
    visibility: VisibilityType
    expires_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SnippetResponse(BaseModel):
    id: UUID
    short_id: str
    title: str
    author: UserMeta
    created_at: datetime
    latest_version: int
    current_version: SnippetVersionResponse

    model_config = ConfigDict(from_attributes=True)


class SnippetOut(BaseModel):
    ttl_seconds: Optional[int] = Field(default=None, ge=60, le=60 * 60 * 24)


class SnippetOutResponse(BaseModel):
    share_url: HttpUrl
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SnippetMetaResponse(BaseModel):
    id: UUID
    short_id: str
    title: str
    author: UserMeta
    latest_version: int = Field(alias="version_counter")
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
