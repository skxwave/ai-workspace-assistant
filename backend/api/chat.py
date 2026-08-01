import json
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from langchain.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from backend.agent.agent import get_agent
from .schemas import ChatRequest

router = APIRouter(tags=["Chat"])


@router.post("/invoke/{thread_id}")
async def chat_invoke(
    request: ChatRequest,
    thread_id: str,
    agent: Annotated[CompiledStateGraph, Depends(get_agent)],
):
    config = {"configurable": {"thread_id": thread_id}}
    input = {"messages": [HumanMessage(content=request.message)]}
    messages = await agent.ainvoke(
        input=input,
        config=config,
    )
    return {
        "message": messages["messages"][-1].content,
        "state": await agent.aget_state(config=config),
    }


@router.post("/stream/{thread_id}")
async def chat_stream(
    request: ChatRequest,
    thread_id: str,
    agent: Annotated[CompiledStateGraph, Depends(get_agent)],
):
    config = {"configurable": {"thread_id": thread_id}}
    input = {"messages": [HumanMessage(content=request.message)]}

    async def event_generator():
        async for chunk in agent.astream(
            input=input,
            config=config,
            stream_mode="messages",
            version="v2",
        ):
            msg, _ = chunk["data"]
            yield f"{msg.content}"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.websocket("/ws/{thread_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    thread_id: str,
    agent: Annotated[CompiledStateGraph, Depends(get_agent)],
):
    await websocket.accept()

    config = {"configurable": {"thread_id": thread_id}}

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            user_message = data.get("message", "")

            if not user_message:
                continue

            input = {"messages": [HumanMessage(user_message)]}

            async for chunk in agent.astream(
                input=input,
                config=config,
                stream_mode="messages",
                version="v2",
            ):
                msg, _ = chunk["data"]
                await websocket.send_json(
                    {
                        "content": msg.content,
                    }
                )

            await websocket.send_json({"type": "end"})
    except WebSocketDisconnect:
        # TODO: change to logger
        print(f"Client disconnected from thread: {thread_id}")
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        await websocket.close()
