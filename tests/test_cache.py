import time

import pytest

from lol_genius.proxy.cache import ProxyCache


@pytest.fixture
def cache():
    c = ProxyCache(max_mb=512)
    yield c
    c.stop()


def test_clear_flushes_all_entries(cache):
    cache.set("ns", "a", "val_a", 300)
    cache.set("ns", "b", "val_b", 300)
    flushed = cache.clear()
    assert flushed == 2
    hit, _ = cache.get("ns", "a")
    assert not hit


def test_byte_limit_evicts_lru(cache):
    cache._max_bytes = 100

    cache.set("ns", "old", "x" * 30, 300)
    cache.set("ns", "recent", "y" * 30, 300)
    cache.get("ns", "recent")  # promotes last_access above "old"

    cache.set("ns", "new", "z" * 50, 300)

    hit_old, _ = cache.get("ns", "old")
    hit_recent, _ = cache.get("ns", "recent")
    assert not hit_old, "LRU entry should have been evicted"
    assert hit_recent, "Recently-accessed entry should survive"


def test_expired_entries_not_returned(cache):
    cache.set("ns", "k", "v", 0.01)
    time.sleep(0.05)
    hit, val = cache.get("ns", "k")
    assert not hit
    assert val is None


def test_stats_includes_bytes(cache):
    cache.set("ns", "k", {"data": "hello"}, 300)
    stats = cache.stats()
    assert stats["total_bytes"] > 0
    assert stats["max_bytes"] == 512 * 1024 * 1024


def test_stop_shuts_down_cleanly():
    c = ProxyCache(max_mb=512)
    assert c._cleanup_thread.is_alive()
    c.stop()
    assert not c._cleanup_thread.is_alive()


def test_evict_expired_clears_stale_bytes(cache):
    cache.set("ns", "k", "x" * 100, 0.01)
    assert cache.stats()["total_bytes"] > 0

    time.sleep(0.05)
    cache.get("ns", "k")  # lazy expiry removal

    assert cache.stats()["total_bytes"] == 0
