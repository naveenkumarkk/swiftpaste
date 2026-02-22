from sqlalchemy import Column, DateTime


class SoftDeleteMixin:
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)