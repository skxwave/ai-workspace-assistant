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
