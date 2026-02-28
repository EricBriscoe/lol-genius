from lol_genius.proxy.cache import ProxyCache


def test_clear_flushes_all_entries():
    cache = ProxyCache()
    cache.set("ns", "a", "val_a", 300)
    cache.set("ns", "b", "val_b", 300)
    flushed = cache.clear()
    assert flushed == 2
    hit, _ = cache.get("ns", "a")
    assert not hit
