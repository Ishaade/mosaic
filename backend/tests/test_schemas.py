import pytest
from pydantic import ValidationError

from app.schemas import ChatRequest, LoginRequest, RegisterRequest


def test_chat_request_accepts_valid_payload():
    req = ChatRequest(persona="friend", message="hello")
    assert req.conversation_id is None


def test_chat_request_rejects_empty_message():
    with pytest.raises(ValidationError):
        ChatRequest(persona="friend", message="")


def test_chat_request_rejects_too_long_message():
    with pytest.raises(ValidationError):
        ChatRequest(persona="friend", message="x" * 2001)


def test_chat_request_rejects_unknown_persona():
    with pytest.raises(ValidationError):
        ChatRequest(persona="robot", message="hi")


def test_chat_request_rejects_client_user_id():
    # user_id must not be accepted on the chat body anymore
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {"persona": "friend", "message": "hi", "user_id": 1}
        )


def test_register_requires_min_password():
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", password="short")


def test_login_email_lowercased():
    req = LoginRequest(email="Ada@Example.COM", password="password123")
    assert req.email == "ada@example.com"
