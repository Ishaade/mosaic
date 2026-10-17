"""
API-level tests. The LLM is mocked so no API key is required.
"""

from unittest.mock import AsyncMock, patch

from app.services.safety import CRISIS_REPLY


def test_create_user(client):
    res = client.post("/users", json={})
    assert res.status_code == 201
    assert "id" in res.json()


def test_ownership_blocks_other_users_messages(client):
    user_a = client.post("/users", json={}).json()["id"]
    user_b = client.post("/users", json={}).json()["id"]

    with patch(
        "app.routers.chat.generate_reply",
        new_callable=AsyncMock,
        return_value="hi there",
    ):
        chat = client.post(
            "/chat",
            json={"persona": "friend", "message": "hello", "user_id": user_a},
        )
    assert chat.status_code == 200
    conv_id = chat.json()["conversation_id"]

    # User B must not read User A's messages
    blocked = client.get(
        f"/conversations/{conv_id}/messages", params={"user_id": user_b}
    )
    assert blocked.status_code == 404

    allowed = client.get(
        f"/conversations/{conv_id}/messages", params={"user_id": user_a}
    )
    assert allowed.status_code == 200
    assert len(allowed.json()) == 2  # user + assistant


def test_crisis_saved_without_calling_llm(client):
    user_id = client.post("/users", json={}).json()["id"]

    with patch(
        "app.routers.chat.generate_reply",
        new_callable=AsyncMock,
    ) as mock_llm:
        res = client.post(
            "/chat",
            json={
                "persona": "therapist",
                "message": "I want to kill myself",
                "user_id": user_id,
            },
        )

    assert res.status_code == 200
    data = res.json()
    assert data["crisis"] is True
    assert data["reply"] == CRISIS_REPLY
    mock_llm.assert_not_called()

    messages = client.get(
        f"/conversations/{data['conversation_id']}/messages",
        params={"user_id": user_id},
    ).json()
    assert messages[-1]["content"] == CRISIS_REPLY


def test_chat_persists_and_returns_conversation_id(client):
    user_id = client.post("/users", json={}).json()["id"]

    with patch(
        "app.routers.chat.generate_reply",
        new_callable=AsyncMock,
        return_value="Nice to meet you",
    ):
        res = client.post(
            "/chat",
            json={"persona": "friend", "message": "Hey", "user_id": user_id},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["conversation_id"] >= 1
    assert body["reply"] == "Nice to meet you"
