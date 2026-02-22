from sqlalchemy import (
    Column,
    String,
    Text,
    ForeignKey,
    Enum as Choice,
    DateTime,
    func,
    CheckConstraint,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.enum import VisibilityType
from app.db.base import Base


class Snippet(Base):
    __tablename__ = "snippets"

    __table_args__ = (
        CheckConstraint("length(short_id) = 8", name="ck_snippets_short_id_len"),
        CheckConstraint(
            "content IS NULL OR length(content) <= 50000",
            name="ck_snippets_content_max_len",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > now()",
            name="ck_snippets_expires_future",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    short_id = Column(String(8), nullable=False, unique=True, index=True)

    content = Column(Text, nullable=True)

    visibility = Column(
        Choice(VisibilityType, name="visibility_type_enum"),
        nullable=False,
        default=VisibilityType.PUBLIC,
    )

    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    is_deleted = Column(Boolean, default=False, nullable=False)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    author = relationship("User", back_populates="snippets")
