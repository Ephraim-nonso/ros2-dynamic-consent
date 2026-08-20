import re

from dynamic_consent_hri.core.session import generate_session_id


def test_session_id_is_anonymous_random_token():
    first = generate_session_id()
    second = generate_session_id()
    assert re.fullmatch(r'session_[0-9a-f]{8}', first)
    assert first != second
