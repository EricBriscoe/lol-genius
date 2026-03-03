from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass


@dataclass
class _Entry:
    value: object
    expires_at: float
    last_access: float
    size_bytes: int


class ProxyCache:
    _MAX_NONE_TTL = 300

    def __init__(self, max_mb: int | None = None):
        if max_mb is None:
            max_mb = int(os.environ.get("PROXY_CACHE_MAX_MB", "512"))
        self._max_bytes = max_mb * 1024 * 1024
        self._store: dict[str, _Entry] = {}
        self._total_bytes = 0
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._stop_event = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, daemon=True, name="cache-cleanup"
        )
        self._cleanup_thread.start()

    def _entry_size(self, value: object) -> int:
        try:
            return len(json.dumps(value).encode())
        except Exception:
            return 512

    def _make_key(self, namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    def _remove(self, key: str) -> None:
        entry = self._store.pop(key, None)
        if entry is not None:
            self._total_bytes -= entry.size_bytes

    def get(self, namespace: str, key: str) -> tuple[bool, object]:
        full_key = self._make_key(namespace, key)
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(full_key)
            if entry is None or entry.expires_at <= now:
                if entry is not None:
                    self._remove(full_key)
                self._misses += 1
                return False, None
            entry.last_access = now
            self._hits += 1
            return True, entry.value

    def set(self, namespace: str, key: str, value: object, ttl: float) -> None:
        if value is None:
            ttl = min(ttl, self._MAX_NONE_TTL)
        full_key = self._make_key(namespace, key)
        now = time.monotonic()
        size = self._entry_size(value)
        with self._lock:
            self._remove(full_key)
            self._evict_to_fit(size)
            self._store[full_key] = _Entry(
                value=value, expires_at=now + ttl, last_access=now, size_bytes=size
            )
            self._total_bytes += size

    def _evict_to_fit(self, needed: int) -> None:
        self._evict_expired()
        if self._total_bytes + needed <= self._max_bytes:
            return
        by_access = sorted(self._store.items(), key=lambda kv: kv[1].last_access)
        for k, _ in by_access:
            if self._total_bytes + needed <= self._max_bytes:
                break
            self._remove(k)

    def _evict_expired(self) -> None:
        now = time.monotonic()
        for k in [k for k, v in self._store.items() if v.expires_at <= now]:
            self._remove(k)

    def _cleanup_loop(self) -> None:
        while not self._stop_event.wait(300):
            with self._lock:
                self._evict_expired()

    def stop(self) -> None:
        self._stop_event.set()
        self._cleanup_thread.join(timeout=10)

    def clear(self) -> int:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            self._total_bytes = 0
            return count

    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "entries": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total else 0.0,
                "total_bytes": self._total_bytes,
                "max_bytes": self._max_bytes,
            }
