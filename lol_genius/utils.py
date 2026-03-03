from __future__ import annotations


def exponential_backoff(attempt: int, base_wait: float = 1.0, max_wait: float = 60.0) -> float:
    return min(base_wait * (2.0**attempt), max_wait)
