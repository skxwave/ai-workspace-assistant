import json
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from langchain.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from backend.agent.agent import get_agent
from backend.auth.dependencies import get_current_active_user
from backend.core.models.user import User
from .schemas import ChatRequest

router = APIRouter(tags=["Chat"])


@router.post("/invoke")
async def chat_invoke(
    request: ChatRequest,
    agent: Annotated[CompiledStateGraph, Depends(get_agent)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    config = {"configurable": {"thread_id": current_user.id}}
    input = {"messages": [HumanMessage(content=request.message)]}
    messages = await agent.ainvoke(
        input=input,
        config=config,
    )
    return {
        "message": messages["messages"][-1].content,
        # Added state for debug. TODO: remove if not needed
        "state": await agent.aget_state(config=config),
    }


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    agent: Annotated[CompiledStateGraph, Depends(get_agent)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    config = {"configurable": {"thread_id": current_user.id}}
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


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    agent: Annotated[CompiledStateGraph, Depends(get_agent)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    await websocket.accept()

    config = {"configurable": {"thread_id": current_user.id}}

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
        print(f"Client disconnected from thread: {current_user.id}")
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        await websocket.close()
