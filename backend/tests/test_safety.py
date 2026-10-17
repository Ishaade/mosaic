from app.services.safety import is_crisis


def test_crisis_phrase_detected():
    assert is_crisis("I want to kill myself") is True


def test_curly_apostrophe_normalized():
    # Phone keyboards often produce ’ instead of '
    assert is_crisis("I don’t want to live") is True


def test_normal_message_not_crisis():
    assert is_crisis("I'm having a hard day but I'll be fine") is False


def test_case_insensitive():
    assert is_crisis("I WANT TO END IT ALL") is True
