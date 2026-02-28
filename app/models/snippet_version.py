import uuid
from sqlalchemy import (
    Column,
    Integer,
    Text,
    ForeignKey,
    DateTime,
    Enum as Choice,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.enum import VisibilityType
from app.db.base import Base

class SnippetVersion(Base):
    __tablename__ = "snippet_versions"
    __table_args__ = (
        UniqueConstraint(
            "snippet_id", "version", name="uq_snippet_versions_snippet_id_version"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    snippet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("snippets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False)

    content = Column(Text, nullable=True)
    visibility = Column(
        Choice(VisibilityType, name="visibility_type_enum"),
        nullable=False,
        default=VisibilityType.PUBLIC,
    )

    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    snippet = relationship("Snippet", back_populates="versions")
    author = relationship("User", back_populates="snippets")