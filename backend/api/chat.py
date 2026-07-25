import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
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


@router.websocket("/ws/{thread_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    thread_id: str,
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
                input,
                config,
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
