from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Persona = Literal["therapist", "tutor", "parent", "friend"]


# --- Users -----------------------------------------------------------------


class UserCreate(BaseModel):
    name: str | None = Field(default=None, max_length=100)


class UserOut(BaseModel):
    id: int
    name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}  # allow building from SQLAlchemy objects


# --- Conversations & messages ----------------------------------------------


class ConversationOut(BaseModel):
    id: int
    user_id: int
    persona: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Chat ------------------------------------------------------------------


class ChatRequest(BaseModel):
    persona: Persona
    message: str = Field(min_length=1, max_length=2000)
    # Required: ties the chat to a row in `users`. NOT real auth — see phase notes.
    user_id: int
    # Optional: omit (or null) to start a new conversation
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    persona: str
    reply: str
    crisis: bool = False
    disclaimer: str | None = None
    user_id: int
    conversation_id: int
