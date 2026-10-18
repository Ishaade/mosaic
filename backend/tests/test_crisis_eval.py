"""Keyword-layer precision/recall on the labeled eval set (no API key)."""

from app.eval.crisis_dataset import CRISIS_EVAL_SET
from app.services.safety import keyword_crisis


def test_keyword_eval_has_high_precision():
    """
    Keyword layer should almost never false-positive on our negatives.
    Recall will be imperfect — subtle rows need the LLM layer.
    """
    y_true = [label for _, label in CRISIS_EVAL_SET]
    y_pred = [keyword_crisis(msg) for msg, _ in CRISIS_EVAL_SET]

    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0

    assert len(CRISIS_EVAL_SET) >= 20
    assert fp == 0, "keyword layer should not flag ordinary negatives"
    assert precision == 1.0
    # At least the clear keyword positives should be caught
    assert recall >= 0.5
    assert fn >= 1  # subtle rows intentionally left for the LLM layer
