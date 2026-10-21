"""Phase 3: memory store, prompt formatting, extraction validation, privacy API."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.memory_extract import ExtractedMemories, extract_facts
from app.services.memory_store import format_memories_for_prompt


def test_add_query_filters_by_user(mem_store):
    mem_store.add_facts(
        user_id=1,
        persona="friend",
        facts=[
            {"kind": "name", "text": "User's name is Sam", "scope": "global"},
            {"kind": "preference", "text": "Likes tea", "scope": "global"},
        ],
    )
    mem_store.add_facts(
        user_id=2,
        persona="friend",
        facts=[{"kind": "name", "text": "User's name is Other", "scope": "global"}],
    )

    hits = mem_store.query(user_id=1, persona="friend", query_text="What is my name?")
    assert hits
    assert all(h.user_id == 1 for h in hits)
    assert not any("Other" in h.text for h in hits)


def test_persona_scope_filter(mem_store):
    mem_store.add_facts(
        user_id=1,
        persona="tutor",
        facts=[
            {
                "kind": "goal",
                "text": "Studying quadratic equations",
                "scope": "persona",
            }
        ],
    )
    mem_store.add_facts(
        user_id=1,
        persona="friend",
        facts=[
            {
                "kind": "preference",
                "text": "Likes hiking",
                "scope": "global",
            }
        ],
    )

    tutor_hits = mem_store.query(
        user_id=1, persona="tutor", query_text="math homework equations"
    )
    tutor_texts = {h.text for h in tutor_hits}
    assert "Studying quadratic equations" in tutor_texts

    # Friend must not retrieve tutor-scoped (scope=persona) facts
    friend_hits = mem_store.query(
        user_id=1, persona="friend", query_text="math homework equations"
    )
    friend_texts = {h.text for h in friend_hits}
    assert "Studying quadratic equations" not in friend_texts
    # Global preference remains available to friend
    assert "Likes hiking" in friend_texts or any("hiking" in t.lower() for t in friend_texts)


def test_format_memories_marks_untrusted():
    from app.services.memory_store import MemoryHit

    block = format_memories_for_prompt(
        [
            MemoryHit(
                id="1",
                text="Likes cats",
                user_id=1,
                persona="friend",
                kind="preference",
                created_at="2026-01-01",
            )
        ]
    )
    assert "untrusted" in block.lower()
    assert "not as instructions" in block.lower() or "DATA only" in block
    assert "Likes cats" in block


def test_extract_facts_validates_json():
    raw = ExtractedMemories.model_validate(
        {
            "facts": [
                {
                    "kind": "name",
                    "text": "User's name is Priya",
                    "scope": "global",
                }
            ]
        }
    )
    assert len(raw.facts) == 1


def test_extract_facts_returns_empty_on_bad_json():
    import asyncio

    with patch(
        "app.services.memory_extract.complete_chat",
        new_callable=AsyncMock,
        return_value="not json at all",
    ):
        facts = asyncio.run(
            extract_facts(
                user_message="Hi",
                assistant_reply="Hello!",
                persona="friend",
            )
        )
    assert facts == []


def test_delete_user_removes_vectors(mem_store):
    mem_store.add_facts(
        user_id=9,
        persona="friend",
        facts=[{"kind": "name", "text": "User's name is X", "scope": "global"}],
    )
    assert mem_store.list_for_user(9)
    deleted = mem_store.delete_user(9)
    assert deleted >= 1
    assert mem_store.list_for_user(9) == []


def test_privacy_list_and_delete_api(client, mem_store, auth_user):
    user, headers = auth_user
    user_id = user["id"]
    mem_store.add_facts(
        user_id=user_id,
        persona="friend",
        facts=[{"kind": "preference", "text": "Prefers dark mode", "scope": "global"}],
    )

    listed = client.get("/memories", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    with patch(
        "app.routers.chat.generate_reply",
        new_callable=AsyncMock,
        return_value="hey",
    ), patch(
        "app.routers.chat.extract_facts",
        new_callable=AsyncMock,
        return_value=[],
    ):
        client.post(
            "/chat",
            headers=headers,
            json={"persona": "friend", "message": "hello"},
        )

    wiped = client.delete("/auth/me", headers=headers)
    assert wiped.status_code == 200
    body = wiped.json()
    assert body["memories_deleted"] >= 1
    assert body["sql"]["users"] == 1

    assert client.get("/auth/me", headers=headers).status_code == 401


def test_delete_one_memory_ownership(client, mem_store, auth_user, other_auth_user):
    user, headers = auth_user
    _other, other_headers = other_auth_user
    ids = mem_store.add_facts(
        user_id=user["id"],
        persona="friend",
        facts=[{"kind": "preference", "text": "Likes tea", "scope": "global"}],
    )
    mem_id = ids[0]

    blocked = client.delete(f"/memories/{mem_id}", headers=other_headers)
    assert blocked.status_code == 404

    ok = client.delete(f"/memories/{mem_id}", headers=headers)
    assert ok.status_code == 200
    assert mem_store.list_for_user(user["id"]) == []


def test_delete_all_memories_keeps_account(client, mem_store, auth_user):
    user, headers = auth_user
    mem_store.add_facts(
        user_id=user["id"],
        persona="friend",
        facts=[{"kind": "preference", "text": "Likes tea", "scope": "global"}],
    )
    wiped = client.delete("/memories", headers=headers)
    assert wiped.status_code == 200
    assert wiped.json()["memories_deleted"] >= 1
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert client.get("/memories", headers=headers).json() == []


def test_crisis_skips_memory_extraction(client, mem_store, auth_user):
    user, headers = auth_user
    user_id = user["id"]

    with patch(
        "app.routers.chat.extract_facts",
        new_callable=AsyncMock,
    ) as mock_extract, patch(
        "app.routers.chat.generate_reply",
        new_callable=AsyncMock,
    ) as mock_llm:
        res = client.post(
            "/chat",
            headers=headers,
            json={
                "persona": "therapist",
                "message": "I want to kill myself",
            },
        )

    assert res.status_code == 200
    assert res.json()["crisis"] is True
    mock_extract.assert_not_called()
    mock_llm.assert_not_called()
    assert mem_store.list_for_user(user_id) == []
