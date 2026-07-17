"""Conversion between epoch seconds and builtin_interfaces/Time."""

from builtin_interfaces.msg import Time


def to_time_msg(epoch_seconds: float | None) -> Time:
    """Convert epoch seconds to a Time message; None becomes zero time."""
    msg = Time()
    if epoch_seconds is not None:
        msg.sec = int(epoch_seconds)
        msg.nanosec = int((epoch_seconds - msg.sec) * 1e9)
    return msg
