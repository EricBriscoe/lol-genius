from __future__ import annotations

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from lol_genius.api.client import APIKeyExpiredError
from lol_genius.proxy.key_pool import COOLDOWN_SECONDS, KeyPool


def _make_pool(n: int = 3) -> KeyPool:
    keys = [f"RGAPI-fake-key-{i}" for i in range(n)]
    with patch("lol_genius.proxy.key_pool.RiotHTTPClient") as MockClient:
        mock_instances = []
        for _ in range(n):
            m = MagicMock()
            m.get.return_value = {"ok": True}
            m.rate_window_usage.return_value = (0, 100)
            mock_instances.append(m)
        MockClient.side_effect = mock_instances
        pool = KeyPool(keys)
    return pool


def test_single_key_works():
    pool = _make_pool(1)
    result, key_idx = pool.get("https://example.com/test")
    assert result == {"ok": True}
    assert key_idx == 0
    assert pool._keys[0].total_requests == 1


def test_round_robin_distributes():
    pool = _make_pool(3)
    for _ in range(6):
        pool.get("https://example.com/test")
    for ks in pool._keys:
        assert ks.total_requests == 2


def test_returns_key_index():
    pool = _make_pool(3)
    indices = []
    for _ in range(3):
        _, key_idx = pool.get("https://example.com/test")
        indices.append(key_idx)
    assert indices == [0, 1, 2]


def test_unhealthy_key_failover():
    pool = _make_pool(3)
    pool._keys[0].client.get.side_effect = APIKeyExpiredError("dead")
    result, key_idx = pool.get("https://example.com/test")
    assert result == {"ok": True}
    assert key_idx == 1
    assert not pool._keys[0].healthy
    assert pool._keys[0].total_errors == 1


def test_all_keys_exhausted_raises():
    pool = _make_pool(2)
    for ks in pool._keys:
        ks.client.get.side_effect = APIKeyExpiredError("dead")
    with pytest.raises(APIKeyExpiredError, match="All API keys exhausted"):
        pool.get("https://example.com/test")


def test_all_keys_within_cooldown_raises():
    pool = _make_pool(2)
    now = time.monotonic()
    for ks in pool._keys:
        ks.healthy = False
        ks.unhealthy_since = now
    with pytest.raises(APIKeyExpiredError, match="All API keys exhausted"):
        pool.get("https://example.com/test")


def test_non_auth_error_propagates_without_marking_unhealthy():
    pool = _make_pool(2)
    pool._keys[0].client.get.side_effect = ConnectionError("network down")
    with pytest.raises(ConnectionError, match="network down"):
        pool.get("https://example.com/test")
    assert pool._keys[0].healthy


def test_cooldown_re_enables_key():
    pool = _make_pool(2)
    pool._keys[0].healthy = False
    pool._keys[0].unhealthy_since = time.monotonic() - COOLDOWN_SECONDS - 1
    pool._index = 0
    result, _ = pool.get("https://example.com/test")
    assert result == {"ok": True}
    assert pool._keys[0].healthy


def test_affinity_routes_to_specified_key():
    pool = _make_pool(3)
    pool._index = 0
    result, key_idx = pool.get("https://example.com/test", key_index=2)
    assert result == {"ok": True}
    assert key_idx == 2
    assert pool._keys[2].total_requests == 1
    assert pool._keys[0].total_requests == 0


def test_affinity_falls_back_when_key_unhealthy():
    pool = _make_pool(3)
    pool._keys[2].healthy = False
    pool._keys[2].unhealthy_since = time.monotonic()
    pool._index = 0
    result, key_idx = pool.get("https://example.com/test", key_index=2)
    assert result == {"ok": True}
    assert key_idx == 0


def test_affinity_falls_back_on_auth_error():
    pool = _make_pool(3)
    pool._keys[2].client.get.side_effect = APIKeyExpiredError("dead")
    pool._index = 0
    result, key_idx = pool.get("https://example.com/test", key_index=2)
    assert result == {"ok": True}
    assert key_idx == 0
    assert not pool._keys[2].healthy


def test_affinity_ignores_invalid_index():
    pool = _make_pool(3)
    pool._index = 0
    result, key_idx = pool.get("https://example.com/test", key_index=99)
    assert result == {"ok": True}
    assert key_idx == 0


def test_affinity_ignores_negative_index():
    pool = _make_pool(3)
    pool._index = 0
    result, key_idx = pool.get("https://example.com/test", key_index=-1)
    assert result == {"ok": True}
    assert key_idx == 0


def test_affinity_key_zero_works():
    pool = _make_pool(3)
    pool._index = 2
    result, key_idx = pool.get("https://example.com/test", key_index=0)
    assert result == {"ok": True}
    assert key_idx == 0
    assert pool._keys[0].total_requests == 1


def test_affinity_reenables_cooled_down_key():
    pool = _make_pool(3)
    pool._keys[1].healthy = False
    pool._keys[1].unhealthy_since = time.monotonic() - COOLDOWN_SECONDS - 1
    result, key_idx = pool.get("https://example.com/test", key_index=1)
    assert result == {"ok": True}
    assert key_idx == 1
    assert pool._keys[1].healthy


def test_affinity_and_round_robin_both_exhausted():
    pool = _make_pool(2)
    for ks in pool._keys:
        ks.client.get.side_effect = APIKeyExpiredError("dead")
    with pytest.raises(APIKeyExpiredError, match="All API keys exhausted"):
        pool.get("https://example.com/test", key_index=0)


def test_status_returns_per_key_info():
    pool = _make_pool(2)
    pool.get("https://example.com/test")
    status = pool.status()
    assert len(status) == 2
    assert all("label" in s and "healthy" in s for s in status)


def test_aggregate_usage():
    pool = _make_pool(2)
    usage = pool.aggregate_usage()
    assert "total_used" in usage
    assert "total_budget" in usage
    assert len(usage["keys"]) == 2


def test_close_closes_all_clients():
    pool = _make_pool(3)
    pool.close()
    for ks in pool._keys:
        ks.client.close.assert_called_once()


def test_empty_keys_raises():
    with pytest.raises(ValueError, match="At least one API key"):
        KeyPool([])


def test_thread_safe_concurrent_access():
    pool = _make_pool(3)
    errors = []

    def worker():
        try:
            for _ in range(50):
                pool.get("https://example.com/test")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    total = sum(ks.total_requests for ks in pool._keys)
    assert total == 250


class TestLoadApiKeys:
    def test_csv_format(self):
        from lol_genius.proxy.app import _load_api_keys

        with patch.dict(os.environ, {"RIOT_API_KEYS": "key1,key2,key3"}, clear=True):
            keys = _load_api_keys()
        assert keys == ["key1", "key2", "key3"]

    def test_csv_with_spaces(self):
        from lol_genius.proxy.app import _load_api_keys

        with patch.dict(
            os.environ, {"RIOT_API_KEYS": " key1 , key2 , key3 "}, clear=True
        ):
            keys = _load_api_keys()
        assert keys == ["key1", "key2", "key3"]

    def test_numbered_format(self):
        from lol_genius.proxy.app import _load_api_keys

        with patch.dict(
            os.environ, {"RIOT_API_KEY_1": "k1", "RIOT_API_KEY_2": "k2"}, clear=True
        ):
            keys = _load_api_keys()
        assert keys == ["k1", "k2"]

    def test_single_key_fallback(self):
        from lol_genius.proxy.app import _load_api_keys

        with patch.dict(os.environ, {"RIOT_API_KEY": "single"}, clear=True):
            keys = _load_api_keys()
        assert keys == ["single"]

    def test_no_keys_raises(self):
        from lol_genius.proxy.app import _load_api_keys

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="No API keys found"):
                _load_api_keys()
