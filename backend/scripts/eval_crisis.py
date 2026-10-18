"""
Evaluate crisis detection precision / recall on the labeled set.

From backend/:
  python scripts/eval_crisis.py           # keywords only (no API key)
  python scripts/eval_crisis.py --llm     # keywords + LLM classifier (needs key)

Precision = TP / (TP + FP)  — of the alarms we raised, how many were correct?
Recall    = TP / (TP + FN)  — of the real crises, how many did we catch?

We bias toward higher recall (fewer missed crises) even if precision drops.
Never prints full message bodies in the summary table (sensitive).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow `python scripts/eval_crisis.py` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.eval.crisis_dataset import CRISIS_EVAL_SET
from app.services.safety import keyword_crisis


def _metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, float]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        (2 * precision * recall / (precision + recall))
        if (precision + recall)
        else 0.0
    )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


async def _predict_llm(message: str) -> bool:
    from app.services.safety import check_crisis

    decision = await check_crisis(message, region="IN")
    return decision.crisis


def main() -> None:
    parser = argparse.ArgumentParser(description="Crisis detection eval")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Include the LLM classifier layer (requires LLM_API_KEY)",
    )
    args = parser.parse_args()

    y_true = [label for _, label in CRISIS_EVAL_SET]
    y_pred: list[bool] = []

    for message, _label in CRISIS_EVAL_SET:
        if args.llm:
            pred = asyncio.run(_predict_llm(message))
        else:
            pred = keyword_crisis(message)
        y_pred.append(pred)

    m = _metrics(y_true, y_pred)
    mode = "keywords+llm" if args.llm else "keywords-only"
    print(f"Crisis eval ({mode}) n={len(CRISIS_EVAL_SET)}")
    print(
        f"  TP={m['tp']} FP={m['fp']} FN={m['fn']} TN={m['tn']}"
    )
    print(
        f"  precision={m['precision']:.3f}  recall={m['recall']:.3f}  f1={m['f1']:.3f}"
    )
    if not args.llm:
        print(
            "  note: subtle positives need --llm; keyword-only recall will be lower."
        )


if __name__ == "__main__":
    main()
