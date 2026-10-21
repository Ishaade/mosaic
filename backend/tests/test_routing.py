"""Stage B: persona router unit + API wiring (LLM mocked)."""

import asyncio
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.services.router import (
    RouteSuggestion,
    filter_suggestion,
    should_attempt_routing,
    suggest_persona,
)


def test_should_attempt_routing_cooldown():
    # With default cooldown=3 → turns 1, 4, 7…
    assert should_attempt_routing(1) is True
    assert should_attempt_routing(2) is False
    assert should_attempt_routing(3) is False
    assert should_attempt_routing(4) is True


def test_filter_same_persona_returns_none():
    raw = RouteSuggestion(
        suggested_persona="friend",
        confidence=0.99,
        reason="casual",
    )
    assert filter_suggestion(raw, current_persona="friend") is None


def test_filter_below_threshold_returns_none():
    raw = RouteSuggestion(
        suggested_persona="tutor",
        confidence=settings.routing_confidence_threshold - 0.01,
        reason="homework",
    )
    assert filter_suggestion(raw, current_persona="friend") is None


def test_filter_accepts_confident_different_persona():
    raw = RouteSuggestion(
        suggested_persona="tutor",
        confidence=0.9,
        reason="Looks like homework",
    )
    out = filter_suggestion(raw, current_persona="friend")
    assert out is not None
    assert out.persona == "tutor"


def test_suggest_persona_returns_none_on_bad_json():
    with patch(
        "app.services.router.complete_chat",
        new_callable=AsyncMock,
        return_value="not json",
    ):
        result = asyncio.run(
            suggest_persona(message="explain gravity", current_persona="friend")
        )
    assert result is None


def test_suggest_persona_parses_valid_json():
    payload = (
        '{"suggested_persona":"tutor","confidence":0.88,'
        '"reason":"Academic question"}'
    )
    with patch(
        "app.services.router.complete_chat",
        new_callable=AsyncMock,
        return_value=payload,
    ) as mock_llm:
        result = asyncio.run(
            suggest_persona(
                message="explain photosynthesis",
                current_persona="friend",
                recent_messages=[{"role": "user", "content": "hi"}],
            )
        )
    assert result is not None
    assert result.suggested_persona == "tutor"
    assert result.confidence == 0.88
    # User content must be delimited as untrusted data in the prompt
    blob = mock_llm.await_args.kwargs["messages"][0]["content"]
    assert "<user_message>" in blob
    assert "<recent_history>" in blob


def test_suggest_persona_fail_open_on_llm_error():
    from app.services.llm import LLMError

    with patch(
        "app.services.router.complete_chat",
        new_callable=AsyncMock,
        side_effect=LLMError(503, "down"),
    ):
        result = asyncio.run(
            suggest_persona(message="hello", current_persona="friend")
        )
    assert result is None


def test_chat_includes_suggestion(client, mem_store, auth_user):
    _user, headers = auth_user
    raw = RouteSuggestion(
        suggested_persona="tutor",
        confidence=0.95,
        reason="Homework help",
    )
    with patch(
        "app.routers.chat.generate_reply",
        new_callable=AsyncMock,
        return_value="Let's learn!",
    ), patch(
        "app.routers.chat.extract_facts",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.routers.chat.suggest_persona",
        new_callable=AsyncMock,
        return_value=raw,
    ):
        res = client.post(
            "/chat",
            headers=headers,
            json={
                "persona": "friend",
                "message": "explain photosynthesis",
            },
        )
    assert res.status_code == 200
    body = res.json()
    assert body["suggestion"] is not None
    assert body["suggestion"]["persona"] == "tutor"
    assert body["suggestion"]["reason"] == "Homework help"


def test_crisis_skips_routing(client, mem_store, auth_user):
    _user, headers = auth_user
    with patch(
        "app.routers.chat.suggest_persona",
        new_callable=AsyncMock,
    ) as mock_route, patch(
        "app.routers.chat.generate_reply",
        new_callable=AsyncMock,
    ), patch(
        "app.routers.chat.extract_facts",
        new_callable=AsyncMock,
    ):
        res = client.post(
            "/chat",
            headers=headers,
            json={
                "persona": "friend",
                "message": "I want to kill myself",
            },
        )
    assert res.status_code == 200
    assert res.json()["crisis"] is True
    assert res.json()["suggestion"] is None
    mock_route.assert_not_called()


def test_routing_eval_dataset_size():
    from app.eval.routing_dataset import ROUTING_EVAL_SET

    assert len(ROUTING_EVAL_SET) >= 20
