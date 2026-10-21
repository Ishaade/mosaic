"""Stage A: registration, login, JWT protection, ownership."""

from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from tests.helpers import register_and_login


def test_register_and_login_flow(client):
    reg = client.post(
        "/auth/register",
        json={"email": "Ada@Example.COM", "password": "password123", "name": "Ada"},
    )
    assert reg.status_code == 201
    body = reg.json()
    assert body["email"] == "ada@example.com"  # stored lowercase
    assert "password" not in body
    assert "password_hash" not in body

    bad = client.post(
        "/auth/login",
        json={"email": "ada@example.com", "password": "wrong-password"},
    )
    assert bad.status_code == 401
    assert bad.json()["detail"] == "Invalid email or password"

    # Unknown email uses the SAME message (no enumeration)
    missing = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Invalid email or password"

    ok = client.post(
        "/auth/login",
        json={"email": "ada@example.com", "password": "password123"},
    )
    assert ok.status_code == 200
    assert "access_token" in ok.json()


def test_register_rejects_short_password(client):
    res = client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "1234567"},
    )
    assert res.status_code == 422


def test_register_rejects_duplicate_email(client):
    client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "password123"},
    )
    again = client.post(
        "/auth/register",
        json={"email": "DUP@example.com", "password": "password123"},
    )
    assert again.status_code == 409


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_valid_token(client, auth_user):
    user, headers = auth_user
    res = client.get("/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == user["id"]
    assert res.json()["email"] == "user@example.com"


def test_expired_token_rejected(client, auth_user):
    user, _headers = auth_user
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_tampered_token_rejected(client, auth_user):
    _user, headers = auth_user
    token = headers["Authorization"].split(" ", 1)[1]
    # Flip last character of the signature
    tampered = token[:-2] + ("a" if token[-2] != "a" else "b") + token[-1]
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert res.status_code == 401


def test_protected_endpoints_reject_missing_token(client):
    assert client.get("/conversations").status_code == 401
    assert client.get("/memories").status_code == 401
    assert (
        client.post(
            "/chat",
            json={"persona": "friend", "message": "hi"},
        ).status_code
        == 401
    )


def test_cannot_read_other_users_conversation(client, mem_store):
    user_a, headers_a = register_and_login(client, "a@example.com")
    _user_b, headers_b = register_and_login(client, "b@example.com")

    from unittest.mock import AsyncMock, patch

    with patch(
        "app.routers.chat.generate_reply",
        new_callable=AsyncMock,
        return_value="hi",
    ), patch(
        "app.routers.chat.extract_facts",
        new_callable=AsyncMock,
        return_value=[],
    ):
        chat = client.post(
            "/chat",
            headers=headers_a,
            json={"persona": "friend", "message": "hello"},
        )
    assert chat.status_code == 200
    conv_id = chat.json()["conversation_id"]

    blocked = client.get(
        f"/conversations/{conv_id}/messages",
        headers=headers_b,
    )
    assert blocked.status_code == 404

    allowed = client.get(
        f"/conversations/{conv_id}/messages",
        headers=headers_a,
    )
    assert allowed.status_code == 200


def test_delete_me_wipes_account(client, mem_store, auth_user):
    user, headers = auth_user
    mem_store.add_facts(
        user_id=user["id"],
        persona="friend",
        facts=[{"kind": "preference", "text": "Likes tea", "scope": "global"}],
    )
    wiped = client.delete("/auth/me", headers=headers)
    assert wiped.status_code == 200
    assert wiped.json()["sql"]["users"] == 1
    assert wiped.json()["memories_deleted"] >= 1

    assert client.get("/auth/me", headers=headers).status_code == 401
