from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain.messages import HumanMessage

from backend.agent.agent import agent
from .schemas import ChatRequest

router = APIRouter(tags=["Chat"])


@router.post("/invoke")
async def chat_invoke(
    request: ChatRequest,
):
    messages = [HumanMessage(content=request.message)]
    return {"message": await agent.ainvoke({"messages": messages})}


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
):
    messages = [HumanMessage(content=request.message)]
    input = {"messages": messages}

    async def event_generator():
        async for chunk in agent.astream(
            input=input,
            stream_mode="messages",
            version="v2",
        ):
            msg, _ = chunk["data"]
            yield f"{msg.content}"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
