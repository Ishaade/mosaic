"""
Region-specific crisis helplines.

Numbers change over time — VERIFY before any public deploy.
Set DEFAULT_REGION via env (see config.py); clients may also pass `region` per request.
"""

# Keys are ISO-ish region codes. "DEFAULT" is the fallback if unknown.
HELPLINES: dict[str, list[str]] = {
    "IN": [
        "India emergency: 112",
        "Tele-MANAS: 14416 (free, 24/7)",
        "iCall: +91-9152987821",
    ],
    "US": [
        "US emergency: 911",
        "988 Suicide & Crisis Lifeline: call or text 988",
        "Crisis Text Line: text HOME to 741741",
    ],
    "GB": [
        "UK emergency: 999",
        "Samaritans: 116 123",
        "Shout: text SHOUT to 85258",
    ],
    "DEFAULT": [
        "Local emergency number (e.g. 112 / 911 / 999)",
        "If you can, tell someone you trust and stay near them",
        "Find a local helpline: https://www.iasp.info/suicidalthoughts/",
    ],
}


def normalize_region(region: str | None) -> str:
    if not region:
        return "DEFAULT"
    code = region.strip().upper()
    return code if code in HELPLINES else "DEFAULT"


def format_helpline_block(region: str | None) -> str:
    code = normalize_region(region)
    lines = HELPLINES[code]
    # Always mention a trusted person + that we are not a replacement for care
    bullets = "\n".join(f"- {line}" for line in lines)
    return (
        f"{bullets}\n"
        "- If you can, reach out to someone you trust and stay near them."
    )


def build_crisis_reply(region: str | None = None) -> str:
    """Fixed crisis message with region-appropriate helplines."""
    return (
        "I'm really sorry you're going through this, and I'm glad you told me. "
        "You deserve support from a real person right now.\n\n"
        f"{format_helpline_block(region)}\n\n"
        "I'm an AI and can't replace that kind of help, but I'm here to keep talking."
    )


THERAPIST_DISCLAIMER = (
    "Mosaic is an AI, not a licensed therapist. It can't diagnose or treat, "
    "and it isn't a substitute for professional care."
)
