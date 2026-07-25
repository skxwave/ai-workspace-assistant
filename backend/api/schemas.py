from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: int = Field(1)
    message: str = Field("Hello, what you can do for me?")
