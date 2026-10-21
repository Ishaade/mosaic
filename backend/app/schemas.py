from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Persona = Literal["therapist", "tutor", "parent", "friend"]


# --- Auth -------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, value: EmailStr) -> str:
        return str(value).lower().strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, value: EmailStr) -> str:
        return str(value).lower().strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiry


class UserOut(BaseModel):
    id: int
    email: str
    name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


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
    # Reject unknown fields (e.g. client-supplied user_id) so identity can't sneak in
    model_config = ConfigDict(extra="forbid")

    persona: Persona
    # Hard length cap — also an injection / cost control
    message: str = Field(min_length=1, max_length=2000)
    # Optional: omit (or null) to start a new conversation
    conversation_id: int | None = None
    # Helpline region override; falls back to settings.default_region
    region: str | None = Field(default=None, max_length=8)
    # user_id is NOT accepted here — it comes only from the JWT (Stage A)


class PersonaSuggestion(BaseModel):
    """Optional nudge from the Stage B router — never auto-applied."""

    persona: Literal["therapist", "tutor", "parent", "friend"]
    reason: str
    confidence: float


class ChatResponse(BaseModel):
    persona: str
    reply: str
    crisis: bool = False
    disclaimer: str | None = None
    user_id: int
    conversation_id: int
    # Which safety layer fired, if any ("keyword" | "llm")
    crisis_layer: str | None = None
    # null when crisis, low confidence, same persona, cooldown, or router failure
    suggestion: PersonaSuggestion | None = None


# --- Memories --------------------------------------------------------------


class MemoryOut(BaseModel):
    id: str
    text: str
    user_id: int
    persona: str
    kind: str
    created_at: str


class DeleteUserDataOut(BaseModel):
    user_id: int
    sql: dict[str, int]
    memories_deleted: int
