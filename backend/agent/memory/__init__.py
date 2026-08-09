import asyncio

from psycopg_pool import AsyncConnectionPool

from backend.core import settings

PGCONF = settings.db.postgres
DB_URI = f"postgresql://{PGCONF.user}:{PGCONF.password}@{PGCONF.host}:{PGCONF.port}/{PGCONF.db}"

connection_pool = AsyncConnectionPool(
    conninfo=DB_URI,
    max_size=20,
    open=False,
    kwargs={"autocommit": True},
)

_checkpointer = None
_store = None
_setup_lock = asyncio.Lock()


async def get_shared_checkpointer():
    """Build checkpointer once, not on every graph compile"""
    global _checkpointer
    if _checkpointer is None:
        from backend.agent.memory.checkpointer import get_checkpointer

        async with _setup_lock:
            if _checkpointer is None:
                _checkpointer = await get_checkpointer(connection_pool)
    return _checkpointer


async def get_shared_store():
    """Build store once, not on every graph compile"""
    global _store
    if _store is None:
        from backend.agent.memory.store import get_store

        async with _setup_lock:
            if _store is None:
                _store = await get_store(connection_pool)
    return _store
