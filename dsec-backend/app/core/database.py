import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from app.core.config import settings

# Convert the DATABASE_URL to use the asyncpg driver.
# Railway's PostgreSQL service provides psycopg2-style URLs, but
# create_async_engine() requires an async driver (asyncpg).
_database_url: str = os.environ.get("DATABASE_URL", settings.DATABASE_URL)
if "postgresql+psycopg2://" in _database_url:
    _database_url = _database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
elif _database_url.startswith("postgres://"):
    _database_url = _database_url.replace("postgres://", "postgresql+asyncpg://", 1)

# Naming conventions for Alembic migrations
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)

engine = create_async_engine(
    _database_url,
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    metadata = metadata


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
