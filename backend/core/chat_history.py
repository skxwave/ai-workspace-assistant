import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models.message import ChatMessage


async def save_message(
    session: AsyncSession, *, owner_id: uuid.UUID, role: str, content: str
) -> ChatMessage:
    message = ChatMessage(owner_id=owner_id, role=role, content=content)
    session.add(message)
    await session.commit()
    return message


async def list_messages(
    session: AsyncSession, *, owner_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[ChatMessage], int]:
    total = await session.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.owner_id == owner_id)
    )

    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.owner_id == owner_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    newest_first = list(result.scalars().all())
    return list(reversed(newest_first)), total or 0


async def delete_owner_messages(session: AsyncSession, *, owner_id: uuid.UUID) -> None:
    await session.execute(delete(ChatMessage).where(ChatMessage.owner_id == owner_id))
    await session.commit()
