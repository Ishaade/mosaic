"""
Crisis / distress detection — two layers.

Layer 1 (keywords): fast, free, deterministic "floor". Expanded with Hinglish.
Layer 2 (LLM classifier): catches subtle phrasing; biased toward false positives.

Keywords run first. If they match we never call the classifier.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.services.helplines import THERAPIST_DISCLAIMER, build_crisis_reply

logger = logging.getLogger(__name__)

# Re-export so existing imports (`from app.services.safety import ...`) keep working
__all__ = [
    "THERAPIST_DISCLAIMER",
    "build_crisis_reply",
    "is_crisis",
    "keyword_crisis",
    "check_crisis",
    "CrisisDecision",
]

# Phrases that suggest self-harm / active crisis. Deliberately broad.
# Hinglish / Hindi romanizations are approximate — interview note: real systems
# need native-script coverage and clinician review.
_CRISIS_PHRASES = [
    # English
    r"kill myself",
    r"suicid(e|al)",
    r"end my life",
    r"want to die",
    r"don'?t want to (live|be alive)",
    r"hurt myself",
    r"self[- ]harm",
    r"no reason to live",
    r"end it all",
    r"better off dead",
    r"take my (own )?life",
    r"cut myself",
    r"can'?t go on (anymore|any more)?",
    r"wish i (was|were) dead",
    # Hinglish / common Indian-English mixes (romanized)
    r"main marna chahta",          # I want to die (masc.)
    r"main marna chahti",          # I want to die (fem.)
    r"marna chahta h[uūû]",
    r"marna chahti h[uūû]",
    r"mujhe marna hai",
    r"jee[n]?e ka mann nahi",      # don't feel like living
    r"jeene ki ich+a nahi",
    r"khudku[sś]hi",               # khudkushi ≈ suicide
    r"khud\s*kushi",
    r"suicide kar",                # "suicide kar lunga/lungi"
    r"jaan de d[uūû]nga",
    r"jaan de d[uūû]ngi",
]

_CRISIS_RE = re.compile("|".join(_CRISIS_PHRASES), re.IGNORECASE)


def _normalize(message: str) -> str:
    # Phone keyboards often type a curly apostrophe; normalize it first
    return message.replace("’", "'").replace("‘", "'")


def keyword_crisis(message: str) -> bool:
    """Layer 1 only — used by eval scripts and tests."""
    return bool(_CRISIS_RE.search(_normalize(message)))


def is_crisis(message: str) -> bool:
    """
    Backward-compatible sync check (keywords only).

    Prefer `check_crisis` in request handlers so the LLM layer also runs.
    """
    return keyword_crisis(message)


@dataclass
class CrisisDecision:
    crisis: bool
    layer: str | None  # "keyword" | "llm" | None
    reply: str | None  # fixed helpline text when crisis else None


async def check_crisis(message: str, region: str | None = None) -> CrisisDecision:
    """
    Full safety gate: keywords first, then LLM classifier for subtle distress.

    Bias: the classifier prompt prefers false positives over misses.
    If the classifier call fails, we do NOT invent a crisis (chat stays up);
    keywords remain the reliable floor. Trade-off documented in phase notes.
    """
    if keyword_crisis(message):
        return CrisisDecision(
            crisis=True,
            layer="keyword",
            reply=build_crisis_reply(region),
        )

    # Import here to avoid circular imports at module load
    from app.services.distress_classifier import classify_distress

    try:
        result = await classify_distress(message)
    except Exception:
        logger.warning("Distress classifier failed; falling back to keywords-only")
        return CrisisDecision(crisis=False, layer=None, reply=None)

    if result.crisis:
        return CrisisDecision(
            crisis=True,
            layer="llm",
            reply=build_crisis_reply(region),
        )
    return CrisisDecision(crisis=False, layer=None, reply=None)


# Default crisis reply for older call sites / tests that expect a constant
CRISIS_REPLY = build_crisis_reply("IN")
