import re

# Phrases that suggest self-harm. Deliberately simple; Phase 4 adds a smarter layer.
_CRISIS_PHRASES = [
    r"kill myself", r"suicid(e|al)", r"end my life", r"want to die",
    r"don'?t want to (live|be alive)", r"hurt myself", r"self[- ]harm",
    r"no reason to live", r"end it all",
]
# Compile once at import time instead of on every request
_CRISIS_RE = re.compile("|".join(_CRISIS_PHRASES), re.IGNORECASE)

# Helplines vary by country and change over time. VERIFY these before deploying,
# and later make them configurable per region.
CRISIS_REPLY = (
    "I'm really sorry you're going through this, and I'm glad you told me. "
    "You deserve support from a real person right now.\n\n"
    "- If you might act on these thoughts or are in immediate danger, call your "
    "local emergency number (112 in India, 911 in the US).\n"
    "- India: Tele-MANAS, 14416 (free, 24/7). US: call or text 988.\n"
    "- If you can, reach out to someone you trust and stay near them.\n\n"
    "I'm an AI and can't replace that kind of help, but I'm here to keep talking."
)

THERAPIST_DISCLAIMER = (
    "Mosaic is an AI, not a licensed therapist. It can't diagnose or treat, "
    "and it isn't a substitute for professional care."
)


def is_crisis(message: str) -> bool:
    # Phone keyboards often type a curly apostrophe; normalize it first
    return bool(_CRISIS_RE.search(message.replace("’", "'")))