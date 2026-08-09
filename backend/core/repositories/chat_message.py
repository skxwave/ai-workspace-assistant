import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.constants import MessageRole
from backend.core.db import get_db
from backend.core.models.message import ChatMessage


class ChatMessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(
        self,
        *,
        owner_id: uuid.UUID,
        role: MessageRole,
        content: str,
        chat_id: uuid.UUID,
    ) -> ChatMessage:
        message = ChatMessage(
            owner_id=owner_id,
            role=role,
            content=content,
            chat_id=chat_id,
        )
        self.session.add(message)
        await self.session.commit()
        return message

    async def list_for_owner(
        self,
        *,
        owner_id: uuid.UUID,
        chat_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[ChatMessage], int]:
        total = await self.session.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(
                ChatMessage.owner_id == owner_id,
                ChatMessage.chat_id == chat_id,
            )
        )

        result = await self.session.execute(
            select(ChatMessage)
            .where(
                ChatMessage.owner_id == owner_id,
                ChatMessage.chat_id == chat_id,
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        newest_first = list(result.scalars().all())
        return list(reversed(newest_first)), total or 0

    async def delete_for_owner(
        self,
        *,
        owner_id: uuid.UUID,
        chat_id: uuid.UUID,
    ) -> None:
        await self.session.execute(
            delete(ChatMessage).where(
                ChatMessage.owner_id == owner_id,
                ChatMessage.chat_id == chat_id,
            )
        )
        await self.session.commit()


def get_chat_message_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChatMessageRepository:
    return ChatMessageRepository(session)
