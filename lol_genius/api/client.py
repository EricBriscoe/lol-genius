from __future__ import annotations

import logging
import re
import time
from collections import deque
from typing import Callable
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

AUTH_BACKOFF_STEPS = [30, 60, 120, 300, 600, 900, 1800]


class APIKeyExpiredError(Exception):
    pass


METHOD_RATE_LIMITS: dict[str, list[tuple[int, int]]] = {
    "summoner-by-puuid":  [(1600, 60)],
    "league-entries":     [(50, 10)],
    "league-by-puuid":    [(20000, 10), (1200000, 600)],
    "league-by-summoner": [(20000, 10), (1200000, 600)],
    "match-ids":          [(2000, 10)],
    "match":              [(2000, 10)],
    "mastery":            [(20000, 10), (1200000, 600)],
    "account-by-riot-id": [(1000, 60)],
    "account-by-puuid":   [(1000, 60)],
    "spectator":          [(20000, 10)],
}

_METHOD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"/lol/summoner/v4/summoners/by-puuid/"), "summoner-by-puuid"),
    (re.compile(r"/lol/league/v4/entries/by-puuid/"), "league-by-puuid"),
    (re.compile(r"/lol/league/v4/entries/by-summoner/"), "league-by-summoner"),
    (re.compile(r"/lol/league/v4/entries/"), "league-entries"),
    (re.compile(r"/lol/match/v5/matches/by-puuid/.+/ids"), "match-ids"),
    (re.compile(r"/lol/match/v5/matches/"), "match"),
    (re.compile(r"/lol/champion-mastery/v4/champion-masteries/by-puuid/.+/by-champion/"), "mastery"),
    (re.compile(r"/lol/champion-mastery/v4/champion-masteries/by-puuid/.+/top"), "mastery"),
    (re.compile(r"/riot/account/v1/accounts/by-riot-id/"), "account-by-riot-id"),
    (re.compile(r"/riot/account/v1/accounts/by-puuid/"), "account-by-puuid"),
    (re.compile(r"/lol/spectator/v5/active-games/"), "spectator"),
]


def resolve_method(url: str) -> str | None:
    path = urlparse(url).path
    for pattern, method_key in _METHOD_PATTERNS:
        if pattern.search(path):
            return method_key
    return None


class RateLimiter:
    def __init__(self, default_buckets: list[tuple[int, int]] | None = None, scale: float = 1.0):
        raw = default_buckets or [(20, 1), (100, 120)]
        self.buckets: list[tuple[int, int]] = [
            (max(1, int(count * scale)), window) for count, window in raw
        ]
        self.timestamps: dict[int, deque[float]] = {
            w: deque() for _, w in self.buckets
        }
        self._min_interval = self._compute_min_interval()
        self._last_request: float = 0.0

    def _compute_min_interval(self) -> float:
        if not self.buckets:
            return 0.0
        intervals = [window / count for count, window in self.buckets]
        return min(intervals)

    def update_limits(self, limit_header: str | None) -> None:
        if not limit_header:
            return
        new_buckets = []
        for part in limit_header.split(","):
            count, window = part.strip().split(":")
            new_buckets.append((int(count), int(window)))
        if new_buckets != self.buckets:
            self.buckets = new_buckets
            self.timestamps = {w: deque() for _, w in self.buckets}
            self._min_interval = self._compute_min_interval()

    def wait_if_needed(self) -> None:
        now = time.monotonic()
        pace_wait = self._last_request + self._min_interval - now
        if pace_wait > 0:
            time.sleep(pace_wait)

        while True:
            now = time.monotonic()
            max_wait = 0.0
            for max_calls, window in self.buckets:
                ts = self.timestamps.get(window, deque())
                while ts and ts[0] < now - window:
                    ts.popleft()
                if len(ts) >= max_calls:
                    wait = ts[0] + window - now + 0.05
                    max_wait = max(max_wait, wait)
            if max_wait <= 0:
                break
            log.debug(f"Rate limit: waiting {max_wait:.1f}s")
            time.sleep(max_wait)

    def record_request(self) -> None:
        now = time.monotonic()
        self._last_request = now
        for _, window in self.buckets:
            if window not in self.timestamps:
                self.timestamps[window] = deque()
            self.timestamps[window].append(now)

    def window_usage(self) -> tuple[int, int]:
        now = time.monotonic()
        ts = self.timestamps.get(120, deque())
        used = sum(1 for t in ts if now - t <= 120)
        budget = next((count for count, window in self.buckets if window == 120), 0)
        return used, budget


class RiotHTTPClient:
    def __init__(self, api_key: str, key_loader: Callable[[], str] | None = None, rate_scale: float = 1.0, auth_backoff: bool = True):
        self.api_key = api_key
        self.key_loader = key_loader
        self._auth_backoff_enabled = auth_backoff
        self._rate_scale = rate_scale
        self.client = httpx.Client(
            headers={"X-Riot-Token": api_key},
            timeout=30.0,
        )
        self.rate_limiter = RateLimiter(scale=rate_scale)
        self.method_limiters: dict[str, RateLimiter] = {}

    def _get_method_limiter(self, method: str) -> RateLimiter:
        if method not in self.method_limiters:
            buckets = METHOD_RATE_LIMITS.get(method, [(20000, 10)])
            self.method_limiters[method] = RateLimiter(default_buckets=buckets, scale=self._rate_scale)
        return self.method_limiters[method]

    def _reload_key(self) -> bool:
        if not self.key_loader:
            return False
        new_key = self.key_loader()
        if new_key and new_key != self.api_key:
            self.api_key = new_key
            self.client.headers["X-Riot-Token"] = new_key
            log.info("API key reloaded from .env")
            return True
        return False

    def _auth_backoff(self, status_code: int) -> None:
        for i, wait in enumerate(AUTH_BACKOFF_STEPS):
            log.warning(
                f"API key rejected ({status_code}). "
                f"Backoff step {i+1}/{len(AUTH_BACKOFF_STEPS)}: waiting {wait}s. "
                f"Update RIOT_API_KEY in .env to resume sooner."
            )
            time.sleep(wait)
            self._reload_key()

            try:
                probe = self.client.get("https://na1.api.riotgames.com/lol/league/v4/entries/RANKED_SOLO_5x5/IRON/I?page=1")
                if probe.status_code not in (401, 403):
                    log.info("API key accepted after backoff")
                    return
            except httpx.RequestError:
                pass

        raise APIKeyExpiredError(
            f"API key still rejected after {len(AUTH_BACKOFF_STEPS)} backoff steps (~63 min). "
            "Generate a new key at https://developer.riotgames.com/"
        )

    def get(self, url: str, max_retries: int = 5) -> dict | list | None:
        method = resolve_method(url)
        method_limiter = self._get_method_limiter(method) if method else None
        limiters = [self.rate_limiter] + ([method_limiter] if method_limiter else [])

        for attempt in range(max_retries):
            for lim in limiters:
                lim.wait_if_needed()

            try:
                response = self.client.get(url)
            except httpx.RequestError as e:
                log.warning(f"Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

            self.rate_limiter.update_limits(response.headers.get("x-app-rate-limit"))
            if method_limiter:
                method_limiter.update_limits(response.headers.get("x-method-rate-limit"))

            if response.status_code == 200:
                for lim in limiters:
                    lim.record_request()
                return response.json()

            if response.status_code == 404:
                for lim in limiters:
                    lim.record_request()
                return None

            if response.status_code in (401, 403):
                if not self._auth_backoff_enabled:
                    raise APIKeyExpiredError(f"API key rejected ({response.status_code})")
                self._auth_backoff(response.status_code)
                continue

            if response.status_code == 429:
                retry_after = float(response.headers.get("retry-after", "5"))
                log.warning(f"429 rate limited, retrying after {retry_after}s")
                time.sleep(retry_after)
                continue

            if response.status_code >= 500:
                wait = min(2 ** attempt, 60)
                log.warning(f"{response.status_code} server error, retrying in {wait}s")
                time.sleep(wait)
                continue

            for lim in limiters:
                lim.record_request()
            body = ""
            try:
                body = response.text[:500]
            except Exception:
                pass
            log.error(f"Unexpected status {response.status_code} for {url}: {body}")
            return None

        log.error(f"Max retries exceeded for {url}")
        return None

    def rate_window_usage(self) -> tuple[int, int]:
        return self.rate_limiter.window_usage()

    def close(self):
        self.client.close()
