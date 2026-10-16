from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    persona: Literal["therapist", "tutor", "parent", "friend"]
    message: str = Field(min_length=1, max_length=2000)
    user_name: str | None = None


class ChatResponse(BaseModel):
    persona: str
    reply: str
    crisis: bool = False
    disclaimer: str | None = None