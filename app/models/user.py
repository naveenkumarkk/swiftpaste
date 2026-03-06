from sqlalchemy.orm import relationship,mapped_column,Mapped
from app.db.base import Base
from fastapi_users.db import SQLAlchemyBaseUserTableUUID #, SQLAlchemyUserDatabase
from sqlalchemy import String

class User(SQLAlchemyBaseUserTableUUID,Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True,nullable=False)
    snippets = relationship(
        "Snippet",
        back_populates="author",
        passive_deletes=True, 
    )
