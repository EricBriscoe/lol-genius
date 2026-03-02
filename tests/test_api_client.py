from unittest.mock import patch

import httpx
import pytest

from lol_genius.api.client import (
    BadRequestError,
    RateLimiter,
    RiotHTTPClient,
    resolve_method,
    METHOD_RATE_LIMITS,
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


def test_rate_limiter_record_request():
    rl = RateLimiter()
    rl.record_request()
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
    def test_method_limiter_created_lazily(self):
        from unittest.mock import patch
        from lol_genius.api.client import RiotHTTPClient

        with patch("lol_genius.api.client.httpx.Client"):
            client = RiotHTTPClient("fake-key", auth_backoff=False)

        assert client.method_limiters == {}
        limiter = client._get_method_limiter("match")
        assert "match" in client.method_limiters
        assert limiter.buckets == [(2000, 10)]

    def test_method_limiter_uses_correct_buckets(self):
        from unittest.mock import patch
        from lol_genius.api.client import RiotHTTPClient

        with patch("lol_genius.api.client.httpx.Client"):
            client = RiotHTTPClient("fake-key", auth_backoff=False)

        limiter = client._get_method_limiter("summoner-by-puuid")
        assert limiter.buckets == [(1600, 60)]

        limiter = client._get_method_limiter("league-entries")
        assert limiter.buckets == [(50, 10)]

    def test_method_limiter_respects_scale(self):
        from unittest.mock import patch
        from lol_genius.api.client import RiotHTTPClient

        with patch("lol_genius.api.client.httpx.Client"):
            client = RiotHTTPClient("fake-key", auth_backoff=False, rate_scale=0.5)

        limiter = client._get_method_limiter("account-by-riot-id")
        assert limiter.buckets == [(500, 60)]

    def test_method_limiter_reused(self):
        from unittest.mock import patch
        from lol_genius.api.client import RiotHTTPClient

        with patch("lol_genius.api.client.httpx.Client"):
            client = RiotHTTPClient("fake-key", auth_backoff=False)

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
            400, text='{"status":{"message":"Exception decrypting"}}',
            request=httpx.Request("GET", "https://example.com"),
        )
        with pytest.raises(BadRequestError, match="400 Bad Request"):
            client.get("https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/stale")

    def test_400_records_rate_limit(self):
        client = self._make_client()
        client.client.get.return_value = httpx.Response(
            400, text="bad",
            request=httpx.Request("GET", "https://example.com"),
        )
        initial_len = len(client.rate_limiter.timestamps.get(1, []))
        with pytest.raises(BadRequestError):
            client.get("https://example.com/unknown")
        assert len(client.rate_limiter.timestamps.get(1, [])) > initial_len
