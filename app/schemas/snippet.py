from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl,ConfigDict
from app.core.enum import VisibilityType
from datetime import datetime
from app.schemas.user import UserRead
class SnippetCreate(BaseModel):
    short_id: str
    content: str = Field(min_length=1, max_length=50000)
    visibility: VisibilityType = VisibilityType.PUBLIC
    expires_at: Optional[datetime] = None
    author_id: Optional[UUID] = None


class SnippetUpdate(BaseModel):
    short_id: Optional[str]
    content: Optional[str] = Field(min_length=1, max_length=50000)
    expires_at: Optional[datetime]



class SnippetResponse(BaseModel):
    id: UUID
    content: str
    visibility: VisibilityType
    author_id: UUID
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    author: UserRead

    model_config = ConfigDict(from_attributes=True)


class SnippetOut(BaseModel):
    ttl_seconds: Optional[int] = Field(
        default=None, ge=60, le=60 * 60 * 24
    )

class SnippetOutResponse(BaseModel):
    share_url: HttpUrl
    expires_at: datetime

    class Config:
        orm_mode = True
