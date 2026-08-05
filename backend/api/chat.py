import json
import os
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import uuid4

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
from langchain.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agent.agent import get_agent
from backend.agent.utils.ingestion import (
    chunk_documents,
    delete_owner_documents,
    get_loader,
    supported_extensions,
)
from backend.agent.utils.rag import vector_store
from backend.auth.dependencies import get_current_active_user
from backend.core.chat_history import delete_owner_messages, list_messages, save_message
from backend.core.constants import MessageRole
from backend.core.db import get_db
from backend.core.models.user import User
from .schemas import ChatRequest, MessageOut, MessagesPage

router = APIRouter(tags=["Chat"])

MAX_UPLOAD_SIZE = 20 * 1024 * 1024


@router.post("/invoke")
async def chat_invoke(
    request: ChatRequest,
    agent: Annotated[CompiledStateGraph, Depends(get_agent)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    config = {"configurable": {"thread_id": current_user.id}}
    input = {
        "messages": [HumanMessage(content=request.message)],
        "attached_file_ids": request.attached_file_ids,
    }
    await save_message(
        session,
        owner_id=current_user.id,
        role=MessageRole.HUMAN,
        content=request.message,
    )
    messages = await agent.ainvoke(
        input=input,
        config=config,
    )
    reply = messages["messages"][-1].content
    await save_message(
        session,
        owner_id=current_user.id,
        role=MessageRole.AI,
        content=reply,
    )
    return {
        "message": reply,
        # Added state for debug. TODO: remove if not needed
        # "state": await agent.aget_state(config=config),
    }


@router.get("/messages", response_model=MessagesPage)
async def get_messages(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    messages, total = await list_messages(
        session,
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
    agent: Annotated[CompiledStateGraph, Depends(get_agent)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    await agent.checkpointer.adelete_thread(str(current_user.id))
    await delete_owner_documents(str(current_user.id))
    await delete_owner_messages(session, owner_id=current_user.id)


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    extension = Path(file.filename).suffix.lower()
    if extension not in supported_extensions():
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type. Supported: {sorted(supported_extensions())}",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File too large")

    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    try:
        docs = get_loader(extension)(tmp_path)
    finally:
        os.unlink(tmp_path)

    file_id = str(uuid4())
    chunks = chunk_documents(
        docs,
        owner_id=str(current_user.id),
        filename=file.filename,
        source_type="chat_upload",
        file_id=file_id,
    )
    await vector_store.aadd_documents(chunks)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "chunks_indexed": len(chunks),
    }


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    agent: Annotated[CompiledStateGraph, Depends(get_agent)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    config = {"configurable": {"thread_id": current_user.id}}
    input = {
        "messages": [HumanMessage(content=request.message)],
        "attached_file_ids": request.attached_file_ids,
    }
    await save_message(
        session,
        owner_id=current_user.id,
        role=MessageRole.HUMAN,
        content=request.message,
    )

    async def event_generator():
        reply_chunks = []
        async for chunk in agent.astream(
            input=input,
            config=config,
            stream_mode="messages",
            version="v2",
        ):
            msg, _ = chunk["data"]
            reply_chunks.append(msg.content)
            yield f"{msg.content}"

        reply = "".join(reply_chunks)
        if reply:
            await save_message(
                session,
                owner_id=current_user.id,
                role=MessageRole.AI,
                content=reply,
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    agent: Annotated[CompiledStateGraph, Depends(get_agent)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    await websocket.accept()

    config = {"configurable": {"thread_id": current_user.id}}

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            user_message = data.get("message", "")
            attached_file_ids = data.get("attached_file_ids")

            if not user_message:
                continue

            input = {
                "messages": [HumanMessage(user_message)],
                "attached_file_ids": attached_file_ids,
            }
            await save_message(
                session,
                owner_id=current_user.id,
                role=MessageRole.HUMAN,
                content=user_message,
            )

            reply_chunks = []
            async for chunk in agent.astream(
                input=input,
                config=config,
                stream_mode="messages",
                version="v2",
            ):
                msg, _ = chunk["data"]
                reply_chunks.append(msg.content)
                await websocket.send_json(
                    {
                        "content": msg.content,
                    }
                )

            reply = "".join(reply_chunks)
            if reply:
                await save_message(
                    session,
                    owner_id=current_user.id,
                    role=MessageRole.AI,
                    content=reply,
                )

            await websocket.send_json({"type": "end"})
    except WebSocketDisconnect:
        # TODO: change to logger
        print(f"Client disconnected from thread: {current_user.id}")
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        await websocket.close()
