from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field("Hello, what you can do for me?")
    attached_file_ids: list[str] | None = Field(None)


class MessageOut(BaseModel):
    id: str | None = None
    type: str
    content: Any


class MessagesPage(BaseModel):
    messages: list[MessageOut]
    total: int
    limit: int
    offset: int
    has_more: bool


class ChatOut(BaseModel):
    id: str | None = None


class ChatsPage(BaseModel):
    chats: list[ChatOut]
    total: int
    limit: int
    offset: int
    has_more: bool
