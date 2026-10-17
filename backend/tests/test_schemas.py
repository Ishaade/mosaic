import pytest
from pydantic import ValidationError

from app.schemas import ChatRequest, UserCreate


def test_chat_request_accepts_valid_payload():
    req = ChatRequest(persona="friend", message="hello", user_id=1)
    assert req.conversation_id is None


def test_chat_request_rejects_empty_message():
    with pytest.raises(ValidationError):
        ChatRequest(persona="friend", message="", user_id=1)


def test_chat_request_rejects_too_long_message():
    with pytest.raises(ValidationError):
        ChatRequest(persona="friend", message="x" * 2001, user_id=1)


def test_chat_request_rejects_unknown_persona():
    with pytest.raises(ValidationError):
        ChatRequest(persona="robot", message="hi", user_id=1)


def test_user_create_name_optional():
    user = UserCreate()
    assert user.name is None
