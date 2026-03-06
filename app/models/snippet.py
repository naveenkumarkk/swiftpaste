from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    Integer,
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
            "title IS NULL OR length(title) <= 1000",
            name="ck_snippets_title_max_len",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    short_id = Column(
        String(8), nullable=False, unique=True, index=True, default=generate_short_id
    )
    title = Column(String, nullable=False, default="")
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    version_counter = Column(Integer, default=1, nullable=False)

    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    versions = relationship("SnippetVersion", back_populates="snippet", lazy="selectin")
    author = relationship("User", back_populates="snippets")
