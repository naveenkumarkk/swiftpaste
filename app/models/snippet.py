from sqlalchemy import Column, String,Text,ForeignKey,Enum as Choice,DateTime,func
from app.core.enum import VisibilityType
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid

class Snippet(Base):
    __tablename__ = "snippets"
    id=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    short_id = Column(String,nullable=False)
    content = Column(Text,nullable=True)
    visibility = Column(
        Choice(VisibilityType,name="visibility_type_enum"),
        nullable=False,
        default="public"
    )
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author = relationship("User",back_populates="snippets")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


