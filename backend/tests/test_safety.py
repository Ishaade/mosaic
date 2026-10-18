from app.services.helplines import build_crisis_reply, normalize_region
from app.services.safety import is_crisis, keyword_crisis


def test_crisis_phrase_detected():
    assert is_crisis("I want to kill myself") is True


def test_curly_apostrophe_normalized():
    assert is_crisis("I don’t want to live") is True


def test_normal_message_not_crisis():
    assert is_crisis("I'm having a hard day but I'll be fine") is False


def test_case_insensitive():
    assert is_crisis("I WANT TO END IT ALL") is True


def test_hinglish_phrases():
    assert keyword_crisis("mujhe marna hai") is True
    assert keyword_crisis("main marna chahta hoon") is True
    assert keyword_crisis("khudkushi karne ka soch raha hoon") is True


def test_homework_frustration_not_keyword_crisis():
    # Subtle life-despair is LLM-layer; this homework line must stay negative for keywords
    assert keyword_crisis("I can't do this calculus problem") is False


def test_helpline_region_in_vs_us():
    assert normalize_region("in") == "IN"
    assert "Tele-MANAS" in build_crisis_reply("IN")
    assert "988" in build_crisis_reply("US")
    assert "Samaritans" in build_crisis_reply("GB")


def test_unknown_region_falls_back():
    reply = build_crisis_reply("ZZ")
    assert "iasp.info" in reply or "emergency" in reply.lower()
