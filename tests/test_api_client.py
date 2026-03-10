import threading
import time
from unittest.mock import patch

import httpx
import pytest

from lol_genius.api.client import (
    METHOD_RATE_LIMITS,
    BadRequestError,
    RateLimiter,
    RiotHTTPClient,
    resolve_method,
)


def test_rate_limiter_initial_buckets():
    rl = RateLimiter()
    assert rl.buckets == [(20, 1), (100, 120)]


def test_rate_limiter_custom_buckets():
    rl = RateLimiter(default_buckets=[(1600, 60)])
    assert rl.buckets == [(1600, 60)]
    assert 60 in rl.timestamps


def test_rate_limiter_custom_buckets_with_scale():
    rl = RateLimiter(default_buckets=[(1000, 60)], scale=0.5)
    assert rl.buckets == [(500, 60)]


def test_rate_limiter_scale_floors_at_one():
    rl = RateLimiter(default_buckets=[(1, 60)], scale=0.01)
    assert rl.buckets == [(1, 60)]


def test_rate_limiter_parse_header():
    rl = RateLimiter()
    rl.update_limits("30:1,200:120")
    assert rl.buckets == [(30, 1), (200, 120)]
    assert 1 in rl.timestamps
    assert 120 in rl.timestamps


def test_rate_limiter_update_limits():
    rl = RateLimiter(default_buckets=[(50, 10)])
    rl.update_limits("100:10")
    assert rl.buckets == [(100, 10)]


def test_rate_limiter_update_limits_none():
    rl = RateLimiter(default_buckets=[(50, 10)])
    rl.update_limits(None)
    assert rl.buckets == [(50, 10)]


def test_rate_limiter_acquire_records_timestamps():
    rl = RateLimiter()
    rl.acquire()
    assert len(rl.timestamps[1]) == 1
    assert len(rl.timestamps[120]) == 1


class TestResolveMethod:
    def test_summoner_by_puuid(self):
        url = "https://na1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/abc123"
        assert resolve_method(url) == "summoner-by-puuid"

    def test_league_entries(self):
        url = "https://na1.api.riotgames.com/lol/league/v4/entries/RANKED_SOLO_5x5/GOLD/I?page=1"
        assert resolve_method(url) == "league-entries"

    def test_league_by_puuid(self):
        url = "https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/abc123"
        assert resolve_method(url) == "league-by-puuid"

    def test_league_by_summoner(self):
        url = "https://na1.api.riotgames.com/lol/league/v4/entries/by-summoner/abc123"
        assert resolve_method(url) == "league-by-summoner"

    def test_match_ids(self):
        url = "https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/abc123/ids?start=0&count=20&queue=420"
        assert resolve_method(url) == "match-ids"

    def test_match(self):
        url = "https://americas.api.riotgames.com/lol/match/v5/matches/NA1_12345"
        assert resolve_method(url) == "match"

    def test_mastery_by_champion(self):
        url = "https://na1.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/abc123/by-champion/236"
        assert resolve_method(url) == "mastery"

    def test_mastery_top(self):
        url = "https://na1.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/abc123/top?count=10"
        assert resolve_method(url) == "mastery"

    def test_account_by_riot_id(self):
        url = "https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/Player/NA1"
        assert resolve_method(url) == "account-by-riot-id"

    def test_account_by_puuid(self):
        url = "https://americas.api.riotgames.com/riot/account/v1/accounts/by-puuid/abc123"
        assert resolve_method(url) == "account-by-puuid"

    def test_unknown_url(self):
        assert resolve_method("https://example.com/unknown/path") is None

    def test_league_by_puuid_not_confused_with_entries(self):
        url = "https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/abc"
        assert resolve_method(url) == "league-by-puuid"


class TestMethodLimiter:
    def _make_client(self, **kwargs):
        with patch("lol_genius.api.client.httpx.Client"):
            return RiotHTTPClient("fake-key", auth_backoff=False, **kwargs)

    def test_method_limiter_created_lazily(self):
        client = self._make_client()
        assert client.method_limiters == {}
        limiter = client._get_method_limiter("match")
        assert "match" in client.method_limiters
        assert limiter.buckets == [(2000, 10)]

    def test_method_limiter_uses_correct_buckets(self):
        client = self._make_client()
        limiter = client._get_method_limiter("summoner-by-puuid")
        assert limiter.buckets == [(1600, 60)]

        limiter = client._get_method_limiter("league-entries")
        assert limiter.buckets == [(50, 10)]

    def test_method_limiter_respects_scale(self):
        client = self._make_client(rate_scale=0.5)
        limiter = client._get_method_limiter("account-by-riot-id")
        assert limiter.buckets == [(500, 60)]

    def test_method_limiter_reused(self):
        client = self._make_client()
        first = client._get_method_limiter("match")
        second = client._get_method_limiter("match")
        assert first is second

    def test_all_methods_have_rate_limits(self):
        expected = {
            "summoner-by-puuid",
            "league-entries",
            "league-by-puuid",
            "league-by-summoner",
            "match-ids",
            "match",
            "mastery",
            "account-by-riot-id",
            "account-by-puuid",
            "spectator",
        }
        assert set(METHOD_RATE_LIMITS.keys()) == expected


class TestRiotHTTPClientGet:
    def _make_client(self):
        with patch("lol_genius.api.client.httpx.Client") as mock_cls:
            client = RiotHTTPClient("fake-key", auth_backoff=False)
            client.client = mock_cls.return_value
            return client

    def test_400_raises_bad_request_error(self):
        client = self._make_client()
        client.client.get.return_value = httpx.Response(
            400,
            text='{"status":{"message":"Exception decrypting"}}',
            request=httpx.Request("GET", "https://example.com"),
        )
        with pytest.raises(BadRequestError, match="400 Bad Request"):
            client.get("https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/stale")

    def test_400_records_rate_limit(self):
        client = self._make_client()
        client.client.get.return_value = httpx.Response(
            400,
            text="bad",
            request=httpx.Request("GET", "https://example.com"),
        )
        initial_len = len(client.rate_limiter.timestamps.get(1, []))
        with pytest.raises(BadRequestError):
            client.get("https://example.com/unknown")
        assert len(client.rate_limiter.timestamps.get(1, [])) > initial_len

    def test_429_records_rate_limit(self):
        client = self._make_client()
        client.client.get.side_effect = [
            httpx.Response(
                429,
                headers={"retry-after": "0"},
                request=httpx.Request("GET", "https://example.com"),
            ),
            httpx.Response(
                200,
                json={"ok": True},
                request=httpx.Request("GET", "https://example.com"),
            ),
        ]
        client.get("https://example.com/unknown")
        assert len(client.rate_limiter.timestamps.get(1, [])) == 2

    def test_5xx_records_rate_limit(self):
        client = self._make_client()
        client.client.get.side_effect = [
            httpx.Response(
                500,
                request=httpx.Request("GET", "https://example.com"),
            ),
            httpx.Response(
                200,
                json={"ok": True},
                request=httpx.Request("GET", "https://example.com"),
            ),
        ]
        with patch("lol_genius.api.client.exponential_backoff", return_value=0):
            client.get("https://example.com/unknown")
        assert len(client.rate_limiter.timestamps.get(1, [])) == 2

    def test_sync_counts_corrects_drift_up(self):
        client = self._make_client()
        client.client.get.return_value = httpx.Response(
            200,
            json={"ok": True},
            headers={"x-app-rate-limit-count": "5:1,10:120"},
            request=httpx.Request("GET", "https://example.com"),
        )
        client.get("https://example.com/unknown")
        now = time.monotonic()
        with client.rate_limiter._lock:
            ts_1 = client.rate_limiter.timestamps.get(1)
            recent = sum(1 for t in ts_1 if now - t <= 1)
        assert recent == 5

    def test_priority_passed_through(self):
        client = self._make_client()
        client.client.get.return_value = httpx.Response(
            200,
            json={"ok": True},
            request=httpx.Request("GET", "https://example.com"),
        )
        rl = client.rate_limiter
        with patch.object(rl, "acquire", wraps=rl.acquire) as mock_acq:
            client.get("https://example.com/unknown", priority="high")
            mock_acq.assert_called_with(priority="high")


class TestAtomicAcquire:
    def test_concurrent_acquire_never_over_commits(self):
        capacity = 5
        rl = RateLimiter(default_buckets=[(capacity, 1)])
        timestamps: list[float] = []
        lock = threading.Lock()
        barrier = threading.Barrier(10)

        def worker():
            barrier.wait()
            rl.acquire()
            with lock:
                timestamps.append(time.monotonic())

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        timestamps.sort()
        for i in range(capacity, len(timestamps)):
            assert timestamps[i] - timestamps[i - capacity] >= 0.9

    def test_acquire_blocks_when_full(self):
        rl = RateLimiter(default_buckets=[(2, 1)])
        rl.acquire()
        rl.acquire()

        blocked = threading.Event()
        finished = threading.Event()

        def worker():
            blocked.set()
            rl.acquire()
            finished.set()

        t = threading.Thread(target=worker)
        t.start()
        blocked.wait()
        time.sleep(0.05)
        assert not finished.is_set()
        t.join(timeout=2)


class TestSyncCounts:
    def test_sync_adds_missing_timestamps(self):
        rl = RateLimiter(default_buckets=[(20, 1), (100, 120)])
        rl.sync_counts("5:1,10:120")
        assert len(rl.timestamps[1]) == 5
        assert len(rl.timestamps[120]) == 10

    def test_sync_removes_excess_timestamps(self):
        rl = RateLimiter(default_buckets=[(20, 1), (100, 120)])
        for _ in range(8):
            rl.acquire()
        rl.sync_counts("3:1,3:120")
        assert len(rl.timestamps[1]) == 3
        assert len(rl.timestamps[120]) == 3

    def test_sync_ignores_unknown_windows(self):
        rl = RateLimiter(default_buckets=[(20, 1)])
        rl.sync_counts("5:1,10:999")
        assert len(rl.timestamps[1]) == 5
        assert 999 not in rl.timestamps

    def test_sync_ignores_bad_header(self):
        rl = RateLimiter(default_buckets=[(20, 1)])
        rl.sync_counts("garbage")
        assert len(rl.timestamps[1]) == 0


class TestUpdateLimitsPreservesTimestamps:
    def test_preserves_timestamps_for_same_windows(self):
        rl = RateLimiter(default_buckets=[(20, 1), (100, 120)])
        rl.acquire()
        rl.acquire()
        assert len(rl.timestamps[1]) == 2
        assert len(rl.timestamps[120]) == 2
        rl.update_limits("30:1,200:120")
        assert len(rl.timestamps[1]) == 2
        assert len(rl.timestamps[120]) == 2

    def test_resets_timestamps_for_new_windows(self):
        rl = RateLimiter(default_buckets=[(20, 1), (100, 120)])
        rl.acquire()
        rl.update_limits("20:2,100:60")
        assert len(rl.timestamps.get(2, [])) == 0
        assert len(rl.timestamps.get(60, [])) == 0
        assert 1 not in rl.timestamps
        assert 120 not in rl.timestamps


class TestPriorityLanes:
    def test_low_priority_backs_off_when_utilized(self):
        rl = RateLimiter(default_buckets=[(10, 1)])
        for _ in range(8):
            rl.acquire()

        start = time.monotonic()
        rl.acquire(priority="low")
        elapsed = time.monotonic() - start
        assert elapsed >= rl._min_interval * 2

    def test_high_priority_not_throttled(self):
        rl = RateLimiter(default_buckets=[(10, 1)])
        for _ in range(8):
            rl.acquire()

        start = time.monotonic()
        rl.acquire(priority="high")
        elapsed = time.monotonic() - start
        # min_interval pacing (~100ms) applies, but no extra priority backoff
        assert elapsed < 0.2
