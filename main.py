from contextlib import asynccontextmanager

from fastapi import Body, FastAPI
from langchain.messages import HumanMessage

from backend.agent.agent import agent
from backend.api.schemas import ChatRequest
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


@app.post("/chat", tags=["Chat"])
async def chat(
    request: ChatRequest,
):
    messages = [HumanMessage(content=request.message)]
    return {"message": await agent.ainvoke({"messages": messages})}
