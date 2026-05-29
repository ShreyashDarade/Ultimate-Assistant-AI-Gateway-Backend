"""Time utilities."""

import time
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


class Timer:
    def __init__(self):
        self._start: float = 0

    def start(self) -> None:
        self._start = time.monotonic()

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._start) * 1000)
