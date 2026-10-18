import asyncio
from unittest.mock import AsyncMock, patch

from app.services.distress_classifier import DistressResult, classify_distress
from app.services.safety import CrisisDecision, check_crisis, keyword_crisis


def test_keyword_short_circuits_classifier(mock_distress_classifier):
    """Obvious crisis must not call the LLM classifier."""

    async def run():
        decision = await check_crisis("I want to kill myself", region="IN")
        assert decision.crisis is True
        assert decision.layer == "keyword"
        assert decision.reply is not None
        mock_distress_classifier.assert_not_called()

    asyncio.run(run())


def test_llm_layer_catches_subtle_distress(mock_distress_classifier):
    mock_distress_classifier.return_value = DistressResult(
        crisis=True, confidence="medium", reason="hopelessness"
    )

    async def run():
        # This line is intentionally NOT in the keyword list
        assert keyword_crisis("I just can't do this anymore") is False
        decision = await check_crisis("I just can't do this anymore", region="US")
        assert decision.crisis is True
        assert decision.layer == "llm"
        assert "988" in (decision.reply or "")

    asyncio.run(run())


def test_classifier_fail_open(mock_distress_classifier):
    mock_distress_classifier.side_effect = RuntimeError("boom")

    async def run():
        decision = await check_crisis("hello there", region="IN")
        assert decision == CrisisDecision(crisis=False, layer=None, reply=None)

    asyncio.run(run())


def test_classify_distress_parses_json():
    with patch(
        "app.services.distress_classifier.complete_chat",
        new_callable=AsyncMock,
        return_value='{"crisis": false, "confidence": "high", "reason": "homework"}',
    ):
        result = asyncio.run(classify_distress("I can't do this calculus"))
    assert result.crisis is False
    assert result.confidence == "high"
