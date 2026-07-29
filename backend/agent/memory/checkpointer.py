from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from backend.core import settings

PGCONF = settings.db.postgres
DB_URI = f"postgresql://{PGCONF.user}:{PGCONF.password}@{PGCONF.host}:{PGCONF.port}/{PGCONF.db}"

connection_pool = AsyncConnectionPool(
    conninfo=DB_URI,
    max_size=20,
    open=False,
    kwargs={"autocommit": True},
)


async def get_checkpointer():
    checkpointer = AsyncPostgresSaver(connection_pool)
    await checkpointer.setup()
    return checkpointer
