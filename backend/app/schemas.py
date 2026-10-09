from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    # Literal = only these exact values are allowed
    persona: Literal["therapist", "tutor", "parent", "friend"]
    # Field adds limits: not empty, not huge (protects cost and memory)
    message: str = Field(min_length=1, max_length=2000)
    user_name: str | None = None

class ChatResponse(BaseModel):
    persona: str
    reply: str