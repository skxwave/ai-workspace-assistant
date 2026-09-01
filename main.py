import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langfuse import Langfuse

from backend.api.auth import router as auth_router
from backend.api.chat import router as chat_router
from backend.core import settings
from backend.core.db import engine as db_engine
from backend.core.redis import redis_client
from backend.agent.integrations import schema_cache
from backend.agent.memory import connection_pool
from backend.agent.utils.rag import init_collection_if_not_exists

logging.basicConfig(
    level=logging.DEBUG if settings.app.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

langfuse_client = Langfuse(
    public_key=settings.langfuse.public_key,
    secret_key=settings.langfuse.secret_key,
    host=settings.langfuse.host,
    tracing_enabled=settings.langfuse.enabled,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Qdrant collection
    await init_collection_if_not_exists()

    # Open the Postgres checkpointer pool now that the event loop is running
    await connection_pool.open()

    # Keep MCP tool schemas warm so no user request pays for discovery
    refresh_task = asyncio.create_task(schema_cache.run_refresh_loop())

    yield

    refresh_task.cancel()
    with suppress(asyncio.CancelledError):
        await refresh_task

    await redis_client.aclose()
    await db_engine.dispose()
    await connection_pool.close()


app = FastAPI(
    debug=settings.app.debug,
    title=settings.app.title,
    description=settings.app.description,
    version=settings.app.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(
    router=chat_router,
    prefix="/chat",
)
app.include_router(
    router=auth_router,
    prefix="/auth",
)


@app.get("/health", tags=["Health"])
async def health():
    return {"health": "ok"}
