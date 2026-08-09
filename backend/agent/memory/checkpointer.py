from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


async def get_checkpointer(connection_pool: AsyncConnectionPool):
    checkpointer = AsyncPostgresSaver(connection_pool)
    await checkpointer.setup()
    return checkpointer
