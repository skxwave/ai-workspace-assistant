from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field("Hello, what you can do for me?")
    attached_file_ids: list[str] | None = Field(None)
