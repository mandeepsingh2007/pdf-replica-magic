from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

_SQLITE_CONNECT_ARGS = {"timeout": 60}


def _engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=settings.DEBUG,
        future=True,
        connect_args=_SQLITE_CONNECT_ARGS if url.startswith("sqlite") else {},
    )


engine: AsyncEngine = _engine(settings.DATABASE_URL)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def reset_engine(database_url: str | None = None) -> None:
    """Reconnect after SQLite file was replaced on disk (Render /data bootstrap)."""
    global engine, async_session
    url = database_url or settings.DATABASE_URL
    await engine.dispose()
    engine = _engine(url)
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    import asyncio

    import app.models  # noqa: F401
    from sqlalchemy.exc import OperationalError

    for attempt in range(12):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                if settings.DATABASE_URL.startswith("sqlite"):
                    await conn.execute(text("PRAGMA busy_timeout=60000"))
                    try:
                        await conn.execute(text("PRAGMA journal_mode=WAL"))
                    except Exception:
                        pass
            return
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt >= 11:
                raise
            await asyncio.sleep(min(2.0 * (attempt + 1), 30.0))
