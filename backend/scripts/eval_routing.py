"""
Evaluate persona-routing accuracy on the labeled set.

From backend/:
  python scripts/eval_routing.py           # needs LLM_API_KEY
  python scripts/eval_routing.py --dry-run # print labels only (no API)

Prints accuracy and a simple confusion summary.
Never prints full user message bodies in the summary (sensitive).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.eval.routing_dataset import ROUTING_EVAL_SET
from app.services.router import suggest_persona


async def _predict(message: str) -> str | None:
    # current_persona="friend" is arbitrary; we score absolute predicted label
    result = await suggest_persona(
        message=message,
        current_persona="friend",
        recent_messages=[],
    )
    return result.suggested_persona if result else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Persona routing eval")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List dataset size / labels without calling the LLM",
    )
    args = parser.parse_args()

    if args.dry_run:
        print(f"Routing eval set n={len(ROUTING_EVAL_SET)}")
        counts: dict[str, int] = defaultdict(int)
        for _msg, label in ROUTING_EVAL_SET:
            counts[label] += 1
        for persona, n in sorted(counts.items()):
            print(f"  {persona}: {n}")
        return

    y_true = [label for _, label in ROUTING_EVAL_SET]
    y_pred: list[str | None] = []
    for message, _label in ROUTING_EVAL_SET:
        y_pred.append(asyncio.run(_predict(message)))

    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    total = len(y_true)
    failed = sum(1 for p in y_pred if p is None)
    accuracy = correct / total if total else 0.0

    # confusion: expected -> predicted counts
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t, p in zip(y_true, y_pred):
        key = p if p is not None else "(none)"
        confusion[t][key] += 1

    print(f"Routing eval n={total}")
    print(f"  accuracy={accuracy:.3f}  correct={correct}  failed_calls={failed}")
    print("  confusion (expected → predicted: count):")
    for expected in sorted(confusion):
        parts = [
            f"{pred}:{n}" for pred, n in sorted(confusion[expected].items())
        ]
        print(f"    {expected}: {', '.join(parts)}")


if __name__ == "__main__":
    main()
