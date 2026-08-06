import json
import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse

from backend.auth.dependencies import get_current_active_user
from backend.core.models.user import User
from backend.core.services.chat import ChatService, get_chat_service
from .schemas import ChatRequest, MessageOut, MessagesPage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


@router.post("/invoke")
async def chat_invoke(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    reply = await chat_service.send_message(
        owner_id=current_user.id,
        message=request.message,
        attached_file_ids=request.attached_file_ids,
    )
    return {"message": reply}


@router.get("/messages", response_model=MessagesPage)
async def get_messages(
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    messages, total = await chat_service.get_history(
        owner_id=current_user.id,
        limit=limit,
        offset=offset,
    )

    return MessagesPage(
        messages=[
            MessageOut(id=str(m.id), type=m.role, content=m.content) for m in messages
        ],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total,
    )


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat(
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    await chat_service.clear(owner_id=current_user.id)


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    return await chat_service.upload_document(owner_id=current_user.id, file=file)


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    async def event_generator():
        async for content in chat_service.stream_message(
            owner_id=current_user.id,
            message=request.message,
            attached_file_ids=request.attached_file_ids,
        ):
            yield content

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    try:
        await websocket.accept()
    except RuntimeError:
        logger.info("Handshake aborted by client (user %s)", current_user.id)
        return

    try:
        while True:
            raw_data = await websocket.receive_text()

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "detail": "Malformed frame",
                    }
                )
                continue

            user_message = data.get("message", "")
            attached_file_ids = data.get("attached_file_ids")

            if not user_message:
                continue

            try:
                async for content in chat_service.stream_message(
                    owner_id=current_user.id,
                    message=user_message,
                    attached_file_ids=attached_file_ids,
                ):
                    await websocket.send_json({"content": content})
            except WebSocketDisconnect:
                raise
            except Exception:
                logger.exception("Streaming failed for user %s", current_user.id)
                await websocket.send_json(
                    {"type": "error", "detail": "The assistant failed to answer."}
                )
            else:
                await websocket.send_json({"type": "end"})
    except WebSocketDisconnect:
        logger.info("Client disconnected from thread: %s", current_user.id)


@router.get("/debug/state")
async def graph_state(
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    state = await chat_service.graph_state(owner_id=current_user.id)
    return {"state": state}
