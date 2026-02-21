from sqlalchemy.orm import relationship
from app.db.base import Base
from fastapi_users.db import SQLAlchemyBaseUserTableUUID #, SQLAlchemyUserDatabase

class User(SQLAlchemyBaseUserTableUUID,Base):
    __tablename__ = "users"
    snippets = relationship(
        "Snippet",
        back_populates="author",
        passive_deletes=True, 
    )
