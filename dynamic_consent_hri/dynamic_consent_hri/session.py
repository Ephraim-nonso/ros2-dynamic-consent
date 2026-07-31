"""Anonymous session identifier generation. No participant information is
ever encoded in the id — it is a random token used only to correlate
consent records and log rows within a single session."""

import uuid


def generate_session_id() -> str:
    return f"session_{uuid.uuid4().hex[:8]}"
