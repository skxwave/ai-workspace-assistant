from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.agent.agent import compile_graph
from backend.api.chat import router as chat_router
from backend.core import settings
from backend.agent.memory.checkpointer import connection_pool
from backend.agent.utils.rag import init_collection_if_not_exists


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Qdrant collection
    await init_collection_if_not_exists()

    # Open the Postgres checkpointer pool now that the event loop is running
    await connection_pool.open()

    # Build the agent graph (tools, LLM chain, checkpointer) once, now that
    # the event loop and its dependent connections are ready
    app.state.agent = await compile_graph()

    yield

    await connection_pool.close()


app = FastAPI(
    debug=settings.app.debug,
    title=settings.app.title,
    description=settings.app.description,
    version=settings.app.version,
    lifespan=lifespan,
)

# Routers
app.include_router(
    router=chat_router,
    prefix="/chat",
)


@app.get("/health", tags=["Health"])
async def health():
    return {"health": "ok"}
