from __future__ import annotations

import httpx
import pytest

from lol_genius.api.client import APIKeyExpiredError, BadRequestError
from lol_genius.api.proxy_client import ProxyClient


def _mock_response(data, key_index: int | None = None, cached: bool = False):
    body = {"data": data, "cached": cached}
    if key_index is not None:
        body["key_index"] = key_index
    return httpx.Response(200, json=body)


class TestPuuidKeyMapping:
    def test_get_match_stores_puuid_keys(self):
        client = ProxyClient("http://localhost:8080")
        match_data = {
            "info": {
                "participants": [
                    {"puuid": "aaa"},
                    {"puuid": "bbb"},
                ]
            }
        }
        client.client = _FakeHTTPClient([_mock_response(match_data, key_index=2)])
        client.get_match("NA1_123")

        assert client._puuid_keys["aaa"] == 2
        assert client._puuid_keys["bbb"] == 2

    def test_get_match_ids_stores_puuid_key(self):
        client = ProxyClient("http://localhost:8080")
        client.client = _FakeHTTPClient(
            [_mock_response(["NA1_1", "NA1_2"], key_index=1)]
        )
        client.get_match_ids("some-puuid")

        assert client._puuid_keys["some-puuid"] == 1

    def test_v4_calls_send_key_index_header(self):
        client = ProxyClient("http://localhost:8080")
        client._puuid_keys["aaa"] = 2
        fake = _FakeHTTPClient([_mock_response([], key_index=2)])
        client.client = fake

        client.get_league_by_puuid("aaa")
        assert fake.last_headers.get("X-Key-Index") == "2"

    def test_v4_calls_no_header_when_unmapped(self):
        client = ProxyClient("http://localhost:8080")
        fake = _FakeHTTPClient([_mock_response([], key_index=0)])
        client.client = fake

        client.get_league_by_puuid("unknown-puuid")
        assert "X-Key-Index" not in fake.last_headers

    def test_summoner_by_puuid_sends_key_index(self):
        client = ProxyClient("http://localhost:8080")
        client._puuid_keys["aaa"] = 3
        fake = _FakeHTTPClient([_mock_response({"id": "s1"}, key_index=3)])
        client.client = fake

        client.get_summoner_by_puuid("aaa")
        assert fake.last_headers.get("X-Key-Index") == "3"

    def test_mastery_calls_send_key_index(self):
        client = ProxyClient("http://localhost:8080")
        client._puuid_keys["aaa"] = 1

        fake = _FakeHTTPClient([_mock_response({"level": 7}, key_index=1)])
        client.client = fake
        client.get_champion_mastery("aaa", 236)
        assert fake.last_headers.get("X-Key-Index") == "1"

        fake2 = _FakeHTTPClient([_mock_response([], key_index=1)])
        client.client = fake2
        client.get_top_masteries("aaa")
        assert fake2.last_headers.get("X-Key-Index") == "1"

    def test_cached_response_no_key_index(self):
        client = ProxyClient("http://localhost:8080")
        cached_resp = httpx.Response(200, json={"data": {"id": "s1"}, "cached": True})
        client.client = _FakeHTTPClient([cached_resp])
        result = client.get_summoner_by_puuid("aaa")
        assert result == {"id": "s1"}

    def test_get_match_no_key_index_skips_mapping(self):
        client = ProxyClient("http://localhost:8080")
        match_data = {"info": {"participants": [{"puuid": "aaa"}]}}
        client.client = _FakeHTTPClient(
            [httpx.Response(200, json={"data": match_data, "cached": True})]
        )
        client.get_match("NA1_123")
        assert "aaa" not in client._puuid_keys

    def test_get_match_empty_participants(self):
        client = ProxyClient("http://localhost:8080")
        match_data = {"info": {"participants": []}}
        client.client = _FakeHTTPClient([_mock_response(match_data, key_index=1)])
        result = client.get_match("NA1_123")
        assert result == match_data

    def test_get_match_participant_missing_puuid(self):
        client = ProxyClient("http://localhost:8080")
        match_data = {"info": {"participants": [{"championName": "Jinx"}]}}
        client.client = _FakeHTTPClient([_mock_response(match_data, key_index=1)])
        client.get_match("NA1_123")
        assert len(client._puuid_keys) == 0

    def test_get_account_stores_puuid_key(self):
        client = ProxyClient("http://localhost:8080")
        account_data = {"puuid": "test-puuid", "gameName": "Player", "tagLine": "NA1"}
        client.client = _FakeHTTPClient([_mock_response(account_data, key_index=2)])
        result = client.get_account_by_riot_id("Player", "NA1")
        assert result == account_data
        assert client._puuid_keys["test-puuid"] == 2

    def test_get_account_no_puuid_skips_mapping(self):
        client = ProxyClient("http://localhost:8080")
        client.client = _FakeHTTPClient([_mock_response(None)])
        client.get_account_by_riot_id("Nobody", "NA1")
        assert len(client._puuid_keys) == 0

    def test_get_active_game_sends_key_index(self):
        client = ProxyClient("http://localhost:8080")
        client._puuid_keys["test-puuid"] = 2
        fake = _FakeHTTPClient([_mock_response({"gameId": 123}, key_index=2)])
        client.client = fake
        client.get_active_game("test-puuid")
        assert fake.last_headers.get("X-Key-Index") == "2"

    def test_get_active_game_no_header_when_unmapped(self):
        client = ProxyClient("http://localhost:8080")
        fake = _FakeHTTPClient([_mock_response(None)])
        client.client = fake
        client.get_active_game("unknown-puuid")
        assert "X-Key-Index" not in fake.last_headers

    def test_account_then_spectator_uses_same_key(self):
        client = ProxyClient("http://localhost:8080")
        account_resp = _mock_response(
            {"puuid": "test-puuid", "gameName": "Player", "tagLine": "NA1"},
            key_index=3,
        )
        spectator_resp = _mock_response({"gameId": 456}, key_index=3)
        fake = _FakeHTTPClient([account_resp, spectator_resp])
        client.client = fake
        client.get_account_by_riot_id("Player", "NA1")
        client.get_active_game("test-puuid")
        assert fake.last_headers.get("X-Key-Index") == "3"


class TestErrorHandling:
    def test_503_raises_api_key_expired(self):
        client = ProxyClient("http://localhost:8080")
        client.client = _FakeHTTPClient(
            [httpx.Response(503, json={"error": "expired"})]
        )
        with pytest.raises(APIKeyExpiredError):
            client.get_summoner_by_puuid("aaa")

    def test_4xx_returns_none(self):
        client = ProxyClient("http://localhost:8080")
        client.client = _FakeHTTPClient([httpx.Response(404, text="not found")])
        result = client.get_summoner_by_puuid("aaa")
        assert result is None

    def test_get_list_returns_empty_on_none(self):
        client = ProxyClient("http://localhost:8080")
        client.client = _FakeHTTPClient([httpx.Response(404, text="not found")])
        result = client.get_league_by_puuid("aaa")
        assert result == []

    def test_400_raises_bad_request_error(self):
        client = ProxyClient("http://localhost:8080")
        client.client = _FakeHTTPClient(
            [httpx.Response(400, text='{"error":"bad_request","detail":"stale puuid"}')]
        )
        with pytest.raises(BadRequestError, match="400 from proxy"):
            client.get_summoner_by_puuid("stale-puuid")


class _FakeHTTPClient:
    def __init__(self, responses: list[httpx.Response]):
        self._responses = list(responses)
        self._call_idx = 0
        self.last_headers: dict = {}

    def get(self, url: str, **kwargs) -> httpx.Response:
        self.last_headers = dict(kwargs.get("headers", {}))
        resp = self._responses[self._call_idx % len(self._responses)]
        self._call_idx += 1
        return resp

    def close(self):
        pass
