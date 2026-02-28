from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class _Entry:
    value: object
    expires_at: float
    last_access: float


class ProxyCache:
    MAX_ENTRIES = 100_000
    NONE_TTL = 300

    def __init__(self):
        self._store: dict[str, _Entry] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    def get(self, namespace: str, key: str) -> tuple[bool, object]:
        full_key = self._make_key(namespace, key)
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(full_key)
            if entry is None or entry.expires_at <= now:
                if entry is not None:
                    del self._store[full_key]
                self._misses += 1
                return False, None
            entry.last_access = now
            self._hits += 1
            return True, entry.value

    def set(self, namespace: str, key: str, value: object, ttl: float) -> None:
        if value is None:
            ttl = min(ttl, self.NONE_TTL)
        full_key = self._make_key(namespace, key)
        now = time.monotonic()
        with self._lock:
            if len(self._store) >= self.MAX_ENTRIES and full_key not in self._store:
                self._evict_lru(self.MAX_ENTRIES // 10)
            self._store[full_key] = _Entry(
                value=value, expires_at=now + ttl, last_access=now
            )

    def _evict_lru(self, count: int) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if v.expires_at <= now]
        for k in expired:
            del self._store[k]
        if len(expired) >= count:
            return
        remaining = count - len(expired)
        by_access = sorted(self._store.items(), key=lambda kv: kv[1].last_access)
        for k, _ in by_access[:remaining]:
            del self._store[k]

    def clear(self) -> int:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "entries": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total else 0.0,
            }
