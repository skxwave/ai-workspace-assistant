from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.core import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    debug=settings.app.debug,
    title=settings.app.title,
    description=settings.app.description,
    version=settings.app.version,
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
async def health():
    return {"health": "ok"}
