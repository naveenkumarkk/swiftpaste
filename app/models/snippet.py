from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    func,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.db.base import Base
from app.db.mixins import SoftDeleteMixin

from app.utils.dep import generate_short_id


class Snippet(SoftDeleteMixin, Base):
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

    short_id = Column(
        String(8), nullable=False, unique=True, index=True, default=generate_short_id
    )

    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    latest_version = Column(Integer, nullable=False, default=1)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    versions = relationship("SnippetVersion", back_populates="snippet", lazy="selectin")
    author = relationship("User", back_populates="snippets")