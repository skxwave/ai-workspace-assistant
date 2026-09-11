import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse

from backend.agent.utils.events import StreamEvent, error_event
from backend.auth.dependencies import get_current_active_user
from backend.core.models.user import User
from backend.core.services.chat import ChatService, TurnResult, get_chat_service
from .schemas import (
    ChatOut,
    ChatReply,
    ChatRequest,
    ChatsPage,
    ConfirmRequest,
    MessageOut,
    MessagesPage,
    PendingConfirmation,
    ToolCallOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


def _sse(event: StreamEvent) -> str:
    return f"data: {json.dumps(event.as_frame())}\n\n"


def _reply(result: TurnResult) -> ChatReply:
    return ChatReply(
        message=result.reply,
        steps=[ToolCallOut(**call) for call in result.steps],
        pending_confirmation=[ToolCallOut(**call) for call in result.pending_calls],
    )


@router.get("")
async def get_chat_list(
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    chats, total = await chat_service.get_chat_list(
        owner_id=current_user.id,
        limit=limit,
        offset=offset,
    )

    return ChatsPage(
        chats=[ChatOut(id=str(c.id), created_at=c.created_at) for c in chats],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total,
    )


@router.post("", response_model=ChatOut)
async def create_chat(
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    chat = await chat_service.create_chat(owner_id=current_user.id)
    return ChatOut(id=str(chat.id), created_at=chat.created_at)


@router.post("/{chat_id}/invoke", response_model=ChatReply)
async def chat_invoke(
    chat_id: UUID,
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    result = await chat_service.send_message(
        owner_id=current_user.id,
        chat_id=chat_id,
        message=request.message,
        attached_file_ids=request.attached_file_ids,
    )
    return _reply(result)


@router.get("/{chat_id}/confirmation", response_model=PendingConfirmation)
async def get_pending_confirmation(
    chat_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    calls = await chat_service.pending_confirmation(chat_id=chat_id)
    return PendingConfirmation(calls=[ToolCallOut(**call) for call in calls])


@router.post("/{chat_id}/confirm", response_model=ChatReply)
async def confirm_tool_call(
    chat_id: UUID,
    request: ConfirmRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    result = await chat_service.resume_message(
        owner_id=current_user.id,
        chat_id=chat_id,
        approved=request.approved,
    )
    return _reply(result)


@router.get("/{chat_id}/messages", response_model=MessagesPage)
async def get_messages(
    chat_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    messages, total = await chat_service.get_chat_history(
        owner_id=current_user.id,
        chat_id=chat_id,
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


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    await chat_service.delete_chat(
        owner_id=current_user.id,
        chat_id=chat_id,
    )


@router.post("/{chat_id}/stream")
async def chat_stream(
    chat_id: UUID,
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    async def event_generator():
        try:
            async for event in chat_service.stream_message(
                owner_id=current_user.id,
                chat_id=chat_id,
                message=request.message,
                attached_file_ids=request.attached_file_ids,
            ):
                yield _sse(event)
        except HTTPException as error:
            yield _sse(error_event(error.detail))
        except Exception:
            logger.exception("Streaming failed for user %s", current_user.id)
            yield _sse(error_event("The assistant failed to answer."))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.websocket("/{chat_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    chat_id: UUID,
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

            if data.get("type") == "confirmation":
                stream = chat_service.resume_stream(
                    owner_id=current_user.id,
                    chat_id=chat_id,
                    approved=bool(data.get("approved")),
                )
            else:
                user_message = data.get("message", "")
                if not user_message:
                    continue
                stream = chat_service.stream_message(
                    owner_id=current_user.id,
                    chat_id=chat_id,
                    message=user_message,
                    attached_file_ids=data.get("attached_file_ids"),
                )

            try:
                async for event in stream:
                    await websocket.send_json(event.as_frame())
            except WebSocketDisconnect:
                raise
            except HTTPException as error:
                await websocket.send_json(error_event(error.detail).as_frame())
            except Exception:
                logger.exception("Streaming failed for user %s", current_user.id)
                await websocket.send_json(
                    error_event("The assistant failed to answer.").as_frame()
                )
    except WebSocketDisconnect:
        logger.info("Client disconnected from thread: %s", current_user.id)


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    return await chat_service.upload_document(owner_id=current_user.id, file=file)
