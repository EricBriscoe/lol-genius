from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from lol_genius.api.client import APIKeyExpiredError, RiotHTTPClient

log = logging.getLogger(__name__)

COOLDOWN_SECONDS = 300


@dataclass
class KeyState:
    client: RiotHTTPClient
    healthy: bool = True
    unhealthy_since: float = 0.0
    total_requests: int = 0
    total_errors: int = 0
    key_label: str = ""


class KeyPool:
    def __init__(self, api_keys: list[str], rate_scale: float = 1.0):
        if not api_keys:
            raise ValueError("At least one API key required")
        self._keys: list[KeyState] = []
        for i, key in enumerate(api_keys):
            client = RiotHTTPClient(key, auth_backoff=False, rate_scale=rate_scale)
            label = f"key_{i}_{key[-8:]}"
            self._keys.append(KeyState(client=client, key_label=label))
        self._index = 0
        self._lock = threading.Lock()
        log.info(f"KeyPool initialized with {len(self._keys)} keys")

    def _try_reenable(self, ks: KeyState) -> None:
        if not ks.healthy and time.monotonic() - ks.unhealthy_since >= COOLDOWN_SECONDS:
            ks.healthy = True
            log.info(f"{ks.key_label} re-enabled after cooldown")

    def _mark_unhealthy(self, ks: KeyState) -> None:
        ks.healthy = False
        ks.unhealthy_since = time.monotonic()
        ks.total_errors += 1

    def _next_healthy(self) -> KeyState | None:
        n = len(self._keys)
        for _ in range(n):
            ks = self._keys[self._index % n]
            self._index = (self._index + 1) % n
            self._try_reenable(ks)
            if ks.healthy:
                return ks
        return None

    def _get_by_index(self, key_index: int) -> KeyState | None:
        if 0 <= key_index < len(self._keys):
            ks = self._keys[key_index]
            self._try_reenable(ks)
            if ks.healthy:
                return ks
        return None

    def get(self, url: str, key_index: int | None = None) -> tuple[dict | list | None, int]:
        if key_index is not None:
            with self._lock:
                ks = self._get_by_index(key_index)
            if ks is not None:
                try:
                    result = ks.client.get(url)
                    with self._lock:
                        ks.total_requests += 1
                    return result, key_index
                except APIKeyExpiredError:
                    with self._lock:
                        self._mark_unhealthy(ks)
                    log.warning(f"{ks.key_label} marked unhealthy, falling back to round-robin")

        attempts = 0
        while attempts < len(self._keys):
            with self._lock:
                ks = self._next_healthy()
                used_index = (self._index - 1) % len(self._keys)
            if ks is None:
                raise APIKeyExpiredError("All API keys exhausted")
            try:
                result = ks.client.get(url)
                with self._lock:
                    ks.total_requests += 1
                return result, used_index
            except APIKeyExpiredError:
                with self._lock:
                    self._mark_unhealthy(ks)
                log.warning(f"{ks.key_label} marked unhealthy")
                attempts += 1
                continue
        raise APIKeyExpiredError("All API keys exhausted")

    def status(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "label": ks.key_label,
                    "healthy": ks.healthy,
                    "total_requests": ks.total_requests,
                    "total_errors": ks.total_errors,
                }
                for ks in self._keys
            ]

    def aggregate_usage(self) -> dict:
        with self._lock:
            per_key = []
            total_used = 0
            total_budget = 0
            for ks in self._keys:
                used, budget = ks.client.rate_window_usage()
                total_used += used
                total_budget += budget
                per_key.append({
                    "label": ks.key_label,
                    "healthy": ks.healthy,
                    "used": used,
                    "budget": budget,
                    "total_requests": ks.total_requests,
                })
            return {
                "total_used": total_used,
                "total_budget": total_budget,
                "keys": per_key,
            }

    def close(self):
        for ks in self._keys:
            ks.client.close()
