import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, UploadFile, status
from langchain.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from backend.agent.agent import get_agent
from backend.agent.utils.ingestion import (
    chunk_documents,
    delete_owner_documents,
    get_loader,
    supported_extensions,
)
from backend.agent.utils.rag import vector_store
from backend.core.constants import MAX_UPLOAD_SIZE, MessageRole
from backend.core.models.message import ChatMessage
from backend.core.repositories import ChatMessageRepository, get_chat_message_repository


class ChatService:
    def __init__(self, agent: CompiledStateGraph, messages_repo: ChatMessageRepository):
        self.agent = agent
        self.messages_repo = messages_repo

    def _config(self, owner_id: UUID) -> dict:
        return {"configurable": {"thread_id": owner_id}}

    async def send_message(
        self,
        *,
        owner_id: UUID,
        message: str,
        attached_file_ids: list[str] | None,
    ) -> str:
        await self.messages_repo.save(
            owner_id=owner_id,
            role=MessageRole.HUMAN,
            content=message,
        )

        result = await self.agent.ainvoke(
            input={
                "messages": [HumanMessage(content=message)],
                "attached_file_ids": attached_file_ids,
            },
            config=self._config(owner_id),
        )
        reply = result["messages"][-1].content
        await self.messages_repo.save(
            owner_id=owner_id,
            role=MessageRole.AI,
            content=reply,
        )
        return reply

    async def stream_message(
        self,
        *,
        owner_id: UUID,
        message: str,
        attached_file_ids: list[str] | None,
    ) -> AsyncIterator[str]:
        await self.messages_repo.save(
            owner_id=owner_id,
            role=MessageRole.HUMAN,
            content=message,
        )

        reply_chunks: list[str] = []
        async for chunk in self.agent.astream(
            input={
                "messages": [HumanMessage(content=message)],
                "attached_file_ids": attached_file_ids,
            },
            config=self._config(owner_id),
            stream_mode="messages",
            version="v2",
        ):
            msg, _ = chunk["data"]
            reply_chunks.append(msg.content)
            yield msg.content

        reply = "".join(reply_chunks)
        if reply:
            await self.messages_repo.save(
                owner_id=owner_id,
                role=MessageRole.AI,
                content=reply,
            )

    async def get_history(
        self, *, owner_id: UUID, limit: int, offset: int
    ) -> tuple[list[ChatMessage], int]:
        return await self.messages_repo.list_for_owner(
            owner_id=owner_id,
            limit=limit,
            offset=offset,
        )

    async def clear(self, *, owner_id: UUID) -> None:
        await self.agent.checkpointer.adelete_thread(str(owner_id))
        await delete_owner_documents(str(owner_id))
        await self.messages_repo.delete_for_owner(owner_id=owner_id)

    async def upload_document(
        self,
        *,
        owner_id: UUID,
        file: UploadFile,
    ) -> dict:
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
            owner_id=str(owner_id),
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


def get_chat_service(
    agent: Annotated[CompiledStateGraph, Depends(get_agent)],
    messages_repo: Annotated[
        ChatMessageRepository, Depends(get_chat_message_repository)
    ],
) -> ChatService:
    return ChatService(agent=agent, messages_repo=messages_repo)
