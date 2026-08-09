import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, UploadFile, status
from langchain.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.graph.state import CompiledStateGraph

from backend.agent.agent import build_agent
from backend.agent.utils.ingestion import (
    chunk_documents,
    get_loader,
    supported_extensions,
)
from backend.agent.utils.rag import vector_store
from backend.agent.utils.tools import get_tools_list
from backend.auth.dependencies import get_current_active_user
from backend.core.constants import MAX_UPLOAD_SIZE, MessageRole
from backend.core.models.chat import Chat
from backend.core.models.message import ChatMessage
from backend.core.models.user import User
from backend.core.repositories import (
    ChatRepository,
    ChatMessageRepository,
    UserIntegrationRepository,
    get_chat_repository,
    get_chat_message_repository,
    get_user_integration_repository,
)


class ChatService:
    def __init__(
        self,
        agent: CompiledStateGraph,
        chat_repo: ChatRepository,
        messages_repo: ChatMessageRepository,
        github_token: str,
        missing_integrations: list[str],
    ):
        self.agent = agent
        self.chat_repo = chat_repo
        self.messages_repo = messages_repo
        self.github_token = github_token
        self.missing_integrations = missing_integrations

    def _config(self, chat_id: UUID) -> dict:
        return {
            "configurable": {
                "thread_id": chat_id,
                "github_token": self.github_token,
                "missing_integrations": self.missing_integrations,
            }
        }

    async def create_chat(
        self,
        *,
        owner_id: UUID,
    ) -> UUID:
        chat = await self.chat_repo.save(owner_id=owner_id)
        return chat.id

    async def send_message(
        self,
        *,
        owner_id: UUID,
        chat_id: UUID,
        message: str,
        attached_file_ids: list[str] | None,
    ) -> str:
        await self.messages_repo.save(
            owner_id=owner_id,
            role=MessageRole.HUMAN,
            content=message,
            chat_id=chat_id,
        )

        result = await self.agent.ainvoke(
            input={
                "messages": [HumanMessage(content=message)],
                "attached_file_ids": attached_file_ids,
            },
            config=self._config(chat_id),
        )
        reply = result["messages"][-1].text
        await self.messages_repo.save(
            owner_id=owner_id,
            role=MessageRole.AI,
            content=reply,
            chat_id=chat_id,
        )
        return reply

    async def stream_message(
        self,
        *,
        owner_id: UUID,
        chat_id: UUID,
        message: str,
        attached_file_ids: list[str] | None,
    ) -> AsyncIterator[str]:
        await self.messages_repo.save(
            owner_id=owner_id,
            role=MessageRole.HUMAN,
            content=message,
            chat_id=chat_id,
        )

        reply_chunks: list[str] = []
        async for chunk in self.agent.astream(
            input={
                "messages": [HumanMessage(content=message)],
                "attached_file_ids": attached_file_ids,
            },
            config=self._config(chat_id),
            stream_mode="messages",
            version="v2",
        ):
            msg, _ = chunk["data"]

            if not isinstance(msg, (AIMessage, AIMessageChunk)):
                continue

            text = msg.text
            if not text:
                continue

            reply_chunks.append(text)
            yield text

        reply = "".join(reply_chunks)
        if reply:
            await self.messages_repo.save(
                owner_id=owner_id,
                role=MessageRole.AI,
                content=reply,
                chat_id=chat_id,
            )

    async def get_chat_history(
        self,
        *,
        owner_id: UUID,
        chat_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[ChatMessage], int]:
        return await self.messages_repo.list_for_owner(
            owner_id=owner_id,
            chat_id=chat_id,
            limit=limit,
            offset=offset,
        )

    async def get_chat_list(
        self,
        *,
        owner_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[Chat], int]:
        return await self.chat_repo.list_for_owner(
            owner_id=owner_id,
            limit=limit,
            offset=offset,
        )

    async def delete_chat(
        self,
        *,
        owner_id: UUID,
        chat_id: UUID,
    ) -> None:
        await self.agent.checkpointer.adelete_thread(str(chat_id))
        # TODO: delete docs per chat somehow (or not delete, and set clean-up cron task to delete files that older than X days)
        # await delete_owner_documents(str(owner_id))
        await self.messages_repo.delete_for_owner(
            owner_id=owner_id,
            chat_id=chat_id,
        )
        await self.chat_repo.delete_for_owner(
            owner_id=owner_id,
            chat_id=chat_id,
        )

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

    async def graph_state(
        self,
        *,
        chat_id: UUID,
    ):
        return await self.agent.aget_state(config=self._config(chat_id))


async def get_chat_service(
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repository)],
    messages_repo: Annotated[
        ChatMessageRepository, Depends(get_chat_message_repository)
    ],
    integration_repo: Annotated[
        UserIntegrationRepository, Depends(get_user_integration_repository)
    ],
) -> ChatService:
    github_token = await integration_repo.get_github_token(current_user.id) or ""
    tokens = {"github": github_token} if github_token else {}
    tools, missing_integrations, expired_integrations = await get_tools_list(tokens)

    if "github" in expired_integrations:
        await integration_repo.clear_github_token(current_user.id)
        github_token = ""

    agent = await build_agent(tools)
    return ChatService(
        agent=agent,
        chat_repo=chat_repo,
        messages_repo=messages_repo,
        github_token=github_token,
        missing_integrations=missing_integrations,
    )
