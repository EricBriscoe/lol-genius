from __future__ import annotations


def exponential_backoff(attempt: int, max_wait: float = 60.0) -> float:
    return min(2.0**attempt, max_wait)
