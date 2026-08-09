from psycopg_pool import AsyncConnectionPool
from langgraph.store.postgres.aio import AsyncPostgresStore


async def get_store(connection_pool: AsyncConnectionPool):
    store = AsyncPostgresStore()
    await store.setup()
    return store
