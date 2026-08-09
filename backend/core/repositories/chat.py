import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import get_db
from backend.core.models.chat import Chat


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, *, owner_id: uuid.UUID) -> Chat:
        chat = Chat(owner_id=owner_id)
        self.session.add(chat)
        await self.session.commit()
        return chat

    async def list_for_owner(
        self,
        *,
        owner_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[Chat], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(Chat).where(Chat.owner_id == owner_id)
        )

        result = await self.session.execute(
            select(Chat)
            .where(Chat.owner_id == owner_id)
            .order_by(Chat.created_at.desc())
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
            delete(Chat).where(
                Chat.owner_id == owner_id,
                Chat.id == chat_id,
            )
        )
        await self.session.commit()


def get_chat_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChatRepository:
    return ChatRepository(session)
