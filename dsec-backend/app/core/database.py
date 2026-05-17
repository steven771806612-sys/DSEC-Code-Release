import os
import re

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from app.core.config import settings


def _make_async_db_url(url: str) -> str:
    """Normalise any PostgreSQL URL variant to use the asyncpg driver.

    Railway (and other providers) may supply URLs in several formats:
      - postgres://...
      - postgresql://...
      - postgresql+psycopg2://...
      - postgresql+asyncpg://...   (already correct)

    This function strips any existing scheme/driver prefix and rebuilds
    the URL as ``postgresql+asyncpg://...`` so that SQLAlchemy's async
    engine always receives a compatible driver string.
    """
    # Replace any driver specifier (e.g. +psycopg2, +psycopg, +pg8000 …)
    # and normalise the scheme to the canonical asyncpg form.
    normalised = re.sub(
        r"^postgres(?:ql)?(?:\+[^:]+)?://",
        "postgresql+asyncpg://",
        url,
        count=1,
    )
    return normalised


_raw_url: str = os.environ.get("DATABASE_URL", settings.DATABASE_URL)
_database_url: str = _make_async_db_url(_raw_url)

print(f"[database] Raw DATABASE_URL scheme : {_raw_url.split('://')[0]}://...")
print(f"[database] Resolved async URL scheme: {_database_url.split('://')[0]}://")

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
