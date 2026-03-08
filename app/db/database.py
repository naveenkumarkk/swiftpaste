from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from collections.abc import AsyncGenerator
import app.db.soft_delete  # noqa: F401
from app.core.config import settings
from app.db.base import Base
from app.metrics.db_metrics import setup_db_metrics

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    connect_args={
        "timeout": settings.DB_CONNECTION_TIMEOUT,  # Connection Establishment Time out
        "server_settings": {
            "statement_timeout": str(
                settings.DB_QUERY_TIMEOUT
            )  # Query Statement Timeout
        },
    },
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Prometheus Metric
setup_db_metrics(engine=engine)
