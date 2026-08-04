from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core import settings

PGCONF = settings.db.postgres
ASYNC_DB_URI = f"postgresql+asyncpg://{PGCONF.user}:{PGCONF.password}@{PGCONF.host}:{PGCONF.port}/{PGCONF.db}"

engine = create_async_engine(ASYNC_DB_URI)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
