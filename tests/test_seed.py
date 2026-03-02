from unittest.mock import MagicMock


from lol_genius.crawler.seed import (
    ENTRIES_PER_PAGE,
    _extract_puuids,
    _fetch_tier_puuids,
    seed_accounts,
    seed_tier,
)


def _make_entries(count, has_puuid=True):
    if has_puuid:
        return [{"puuid": f"puuid_{i}"} for i in range(count)]
    return [{"summonerId": f"summ_{i}"} for i in range(count)]


def test_extract_puuids_direct():
    api = MagicMock()
    entries = [{"puuid": "a"}, {"puuid": "b"}, {"puuid": "c"}]
    result = _extract_puuids(api, entries)
    assert result == ["a", "b", "c"]
    api.get_summoner_by_id.assert_not_called()


def test_extract_puuids_fallback_to_summoner_id():
    api = MagicMock()
    api.get_summoner_by_id.side_effect = lambda sid: {"puuid": f"resolved_{sid}"}
    entries = [{"summonerId": "s1"}, {"summonerId": "s2"}]
    result = _extract_puuids(api, entries)
    assert result == ["resolved_s1", "resolved_s2"]


def test_extract_puuids_mixed():
    api = MagicMock()
    api.get_summoner_by_id.return_value = {"puuid": "resolved"}
    entries = [{"puuid": "direct"}, {"summonerId": "s1"}, {}]
    result = _extract_puuids(api, entries)
    assert result == ["direct", "resolved"]


def test_extract_puuids_failed_lookup():
    api = MagicMock()
    api.get_summoner_by_id.return_value = None
    entries = [{"summonerId": "s1"}]
    result = _extract_puuids(api, entries)
    assert result == []


def test_fetch_tier_puuids_round_robin():
    api = MagicMock()
    divisions = ["I", "II"]

    call_count = {"I": 0, "II": 0}

    def mock_entries(tier, division, page):
        call_count[division] += 1
        return [{"puuid": f"{division}_p{page}_{i}"} for i in range(ENTRIES_PER_PAGE)]

    api.get_league_entries.side_effect = mock_entries

    result = _fetch_tier_puuids(api, "GOLD", divisions, target=500)
    assert len(result) == 500
    assert call_count["I"] >= 1
    assert call_count["II"] >= 1


def test_fetch_tier_puuids_exhausts_division():
    api = MagicMock()
    call_log = []

    def mock_entries(tier, division, page):
        call_log.append((division, page))
        if division == "I":
            if page == 1:
                return [{"puuid": f"I_{i}"} for i in range(50)]
            return []
        return [{"puuid": f"II_p{page}_{i}"} for i in range(ENTRIES_PER_PAGE)]

    api.get_league_entries.side_effect = mock_entries

    result = _fetch_tier_puuids(api, "SILVER", ["I", "II"], target=300)
    assert len(result) == 300

    i_pages = [p for d, p in call_log if d == "I"]
    assert max(i_pages) <= 2


def test_fetch_tier_puuids_empty_response_marks_exhausted():
    api = MagicMock()
    api.get_league_entries.return_value = []
    result = _fetch_tier_puuids(api, "IRON", ["I", "II", "III", "IV"], target=100)
    assert result == []


def test_fetch_tier_puuids_all_divisions_exhausted_before_target():
    api = MagicMock()

    def mock_entries(tier, division, page):
        if page == 1:
            return [{"puuid": f"{division}_{i}"} for i in range(5)]
        return []

    api.get_league_entries.side_effect = mock_entries
    result = _fetch_tier_puuids(api, "DIAMOND", ["I", "II"], target=1000)
    assert len(result) == 10


def test_fetch_tier_puuids_truncates_to_target():
    api = MagicMock()
    api.get_league_entries.return_value = [
        {"puuid": f"p_{i}"} for i in range(ENTRIES_PER_PAGE)
    ]

    result = _fetch_tier_puuids(api, "GOLD", ["I"], target=50)
    assert len(result) == 50


def test_fetch_tier_puuids_single_division():
    api = MagicMock()
    pages_fetched = []

    def mock_entries(tier, division, page):
        pages_fetched.append(page)
        return [{"puuid": f"p{page}_{i}"} for i in range(ENTRIES_PER_PAGE)]

    api.get_league_entries.side_effect = mock_entries
    result = _fetch_tier_puuids(api, "BRONZE", ["I"], target=500)
    assert len(result) == 500
    assert len(pages_fetched) == 3


def test_fetch_tier_puuids_short_page_marks_exhausted():
    api = MagicMock()
    call_count = [0]

    def mock_entries(tier, division, page):
        call_count[0] += 1
        if page == 1:
            return [{"puuid": f"p_{i}"} for i in range(100)]
        return []

    api.get_league_entries.side_effect = mock_entries

    result = _fetch_tier_puuids(api, "GOLD", ["I"], target=500)
    assert len(result) == 100
    assert call_count[0] == 1


def test_seed_accounts_calls_per_tier():
    api = MagicMock()
    db = MagicMock()
    db.add_puuids_to_queue.return_value = 100

    config = MagicMock()
    config.target_tiers = ["GOLD", "SILVER"]
    config.target_divisions = ["I", "II", "III", "IV"]
    config.seed_pages = 1

    api.get_league_entries.return_value = [
        {"puuid": f"p_{i}"} for i in range(ENTRIES_PER_PAGE)
    ]

    seed_accounts(api, db, config)

    assert db.add_puuids_to_queue.call_count == 2
    calls = db.add_puuids_to_queue.call_args_list
    for c in calls:
        assert c.kwargs["tier"] in ("GOLD", "SILVER")


def test_seed_accounts_per_tier_target_calculation():
    api = MagicMock()
    db = MagicMock()
    db.add_puuids_to_queue.return_value = 0

    config = MagicMock()
    config.target_tiers = ["GOLD"]
    config.target_divisions = ["I", "II"]
    config.seed_pages = 2

    api.get_league_entries.return_value = [
        {"puuid": f"p_{i}"} for i in range(ENTRIES_PER_PAGE)
    ]

    seed_accounts(api, db, config)

    puuids_arg = db.add_puuids_to_queue.call_args[0][0]
    expected_target = 2 * ENTRIES_PER_PAGE * 2
    assert len(puuids_arg) == expected_target


def test_seed_tier_reuses_helper():
    api = MagicMock()
    db = MagicMock()
    db.add_puuids_to_queue.return_value = 50

    config = MagicMock()
    config.target_divisions = ["I", "II"]

    api.get_league_entries.return_value = [
        {"puuid": f"p_{i}"} for i in range(ENTRIES_PER_PAGE)
    ]

    result = seed_tier(api, db, config, "PLATINUM", pages=1)
    assert result == 50
    db.add_puuids_to_queue.assert_called_once()
    assert db.add_puuids_to_queue.call_args.kwargs["tier"] == "PLATINUM"
