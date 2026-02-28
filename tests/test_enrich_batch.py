from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

from lol_genius.db.queries import MatchDB
from lol_genius.crawler.enrich import (
    EnrichResult,
    check_enrich_needed,
    fetch_enrichment,
    write_enrichment,
)


def _make_participant(match_id, i, puuid=None, team_id=None, win=None):
    tid = team_id if team_id is not None else (100 if i < 5 else 200)
    w = win if win is not None else (1 if i < 5 else 0)
    return {
        "match_id": match_id,
        "puuid": puuid or f"puuid_{i}",
        "summoner_id": f"summ_{i}",
        "team_id": tid,
        "champion_id": i + 1,
        "champion_name": f"Champ{i}",
        "team_position": ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"][i % 5],
        "win": w,
        "kills": 5, "deaths": 3, "assists": 7,
        "total_damage": 20000, "cs": 180,
        "vision_score": 25, "gold_earned": 12000,
        "summoner1_id": 4, "summoner2_id": 14,
        "summoner_level": 200,
        "perks_primary_style": 8100, "perks_sub_style": 8300,
        "perks_keystone": 8112, "perks_offense": 5008, "perks_flex": 5008, "perks_defense": 5002,
        "magic_damage_to_champions": 8000,
        "physical_damage_to_champions": 10000,
        "true_damage_to_champions": 2000,
        "total_damage_taken": 15000,
        "damage_self_mitigated": 8000,
        "wards_placed": 10, "wards_killed": 3,
        "detector_wards_placed": 2,
        "gold_spent": 11000,
        "time_ccing_others": 20,
        "total_heal": 5000,
        "total_heals_on_teammates": 1000,
        "double_kills": 1, "triple_kills": 0,
        "quadra_kills": 0, "penta_kills": 0,
        "largest_killing_spree": 5,
        "item0": 3071, "item1": 3047, "item2": 3026, "item3": 3053,
        "item4": 3065, "item5": 3075, "item6": 3340,
        "neutral_minions_killed": 30, "total_minions_killed": 150,
        "champion_level": 16,
    }


def _make_match(match_id="NA1_123", blue_win=1, game_creation=1700000000000, game_duration=1800):
    return {
        "match_id": match_id,
        "game_version": "14.10.1",
        "patch": "14.10",
        "game_duration": game_duration,
        "queue_id": 420,
        "blue_win": blue_win,
        "game_creation": game_creation,
        "game_start_timestamp": game_creation,
        "game_end_timestamp": game_creation + game_duration * 1000,
        "platform_id": "NA1",
    }


def test_check_enrich_needed_all_missing(db):
    needs, precomputed = check_enrich_needed(db, "new_puuid", "summ_1")
    assert needs["rank"] is True
    assert needs["mastery"] is True
    assert needs["stats"] is True
    assert precomputed is None


def test_check_enrich_needed_all_present(db):
    db.insert_summoner_rank({
        "puuid": "p1", "summoner_id": "s1", "queue_type": "RANKED_SOLO_5x5",
        "tier": "GOLD", "rank": "II", "league_points": 50,
        "wins": 10, "losses": 5,
        "veteran": 0, "inactive": 0, "fresh_blood": 0, "hot_streak": 0,
    })
    db.insert_champion_mastery_batch([{
        "puuid": "p1", "champion_id": 1, "mastery_level": 7,
        "mastery_points": 100000, "last_play_time": None,
        "champion_points_until_next_level": None,
    }])
    db.upsert_player_recent_stats({
        "puuid": "p1", "games_played": 5, "wins": 3,
        "avg_kills": 5.0, "avg_deaths": 3.0, "avg_assists": 7.0,
        "avg_cs_per_min": 6.0, "avg_vision": 25.0, "avg_damage_share": 0.25,
        "avg_wards_placed": 10.0, "avg_wards_killed": 3.0,
        "avg_damage_taken": 15000.0, "avg_gold_spent": 11000.0,
        "avg_cc_score": 20.0, "avg_heal_total": 5000.0,
        "avg_magic_dmg_share": 0.4, "avg_phys_dmg_share": 0.5,
        "avg_multikill_rate": 0.5,
    })

    needs, precomputed = check_enrich_needed(db, "p1", "s1")
    assert needs["rank"] is False
    assert needs["mastery"] is False
    assert needs["stats"] is False
    assert precomputed is None


def test_check_enrich_needed_precomputes_stats(db):
    match = _make_match("NA1_PRE")
    participants = [_make_participant("NA1_PRE", i, puuid="stat_p1" if i == 0 else f"filler_{i}") for i in range(10)]
    db.insert_match(match, participants)

    db.insert_summoner_rank({
        "puuid": "stat_p1", "summoner_id": "s1", "queue_type": "RANKED_SOLO_5x5",
        "tier": "GOLD", "rank": "II", "league_points": 50,
        "wins": 10, "losses": 5,
        "veteran": 0, "inactive": 0, "fresh_blood": 0, "hot_streak": 0,
    })
    db.insert_champion_mastery_batch([{
        "puuid": "stat_p1", "champion_id": 1, "mastery_level": 7,
        "mastery_points": 100000, "last_play_time": None,
        "champion_points_until_next_level": None,
    }])

    needs, precomputed = check_enrich_needed(db, "stat_p1", "s1")
    assert needs["rank"] is False
    assert needs["mastery"] is False
    assert needs["stats"] is False
    assert precomputed is not None
    assert precomputed["games_played"] == 1


def test_fetch_enrichment_with_mock_api():
    api = MagicMock()
    api.get_league_by_puuid.return_value = [
        {"queueType": "RANKED_SOLO_5x5", "tier": "PLATINUM", "rank": "I",
         "leaguePoints": 75, "wins": 50, "losses": 40}
    ]
    api.get_top_masteries.return_value = [
        {"championId": 1, "championLevel": 7, "championPoints": 200000}
    ]
    api.get_match_ids.return_value = []

    needs = {"rank": True, "mastery": True, "stats": True}
    result = fetch_enrichment(api, "p1", "s1", needs)

    assert result.puuid == "p1"
    assert result.rank_entry is not None
    assert result.rank_entry["tier"] == "PLATINUM"
    assert result.league_raw_json is not None
    assert result.mastery_records is not None
    assert len(result.mastery_records) == 1
    assert result.mastery_raw_entries is not None


def test_fetch_enrichment_skips_unnecessary():
    api = MagicMock()

    needs = {"rank": False, "mastery": False, "stats": False}
    result = fetch_enrichment(api, "p1", "s1", needs)

    assert result.rank_entry is None
    assert result.mastery_records is None
    assert result.recent_stats is None
    api.get_league_by_puuid.assert_not_called()
    api.get_top_masteries.assert_not_called()


def test_write_enrichment_persists(db):
    result = EnrichResult(
        puuid="write_p1",
        summoner_id="s1",
        rank_entry={
            "puuid": "write_p1", "summoner_id": "s1",
            "queue_type": "RANKED_SOLO_5x5", "tier": "DIAMOND", "rank": "IV",
            "league_points": 30, "wins": 20, "losses": 15,
            "veteran": 0, "inactive": 0, "fresh_blood": 0, "hot_streak": 0,
        },
        mastery_records=[{
            "puuid": "write_p1", "champion_id": 99, "mastery_level": 5,
            "mastery_points": 50000, "last_play_time": None,
            "champion_points_until_next_level": None,
        }],
        recent_stats={
            "puuid": "write_p1", "games_played": 3, "wins": 2,
            "avg_kills": 6.0, "avg_deaths": 4.0, "avg_assists": 8.0,
            "avg_cs_per_min": 7.0, "avg_vision": 30.0, "avg_damage_share": 0.28,
            "avg_wards_placed": 12.0, "avg_wards_killed": 4.0,
            "avg_damage_taken": 16000.0, "avg_gold_spent": 12000.0,
            "avg_cc_score": 22.0, "avg_heal_total": 5500.0,
            "avg_magic_dmg_share": 0.4, "avg_phys_dmg_share": 0.5,
            "avg_multikill_rate": 0.6,
        },
    )

    write_enrichment(db, result)

    rank = db.get_latest_rank("write_p1")
    assert rank is not None
    assert rank["tier"] == "DIAMOND"

    assert db.has_mastery_data("write_p1")

    stats = db.get_player_recent_stats("write_p1")
    assert stats is not None
    assert stats["games_played"] == 3


def test_fetch_enrichment_empty_api_results():
    api = MagicMock()
    api.get_league_by_puuid.return_value = []
    api.get_top_masteries.return_value = []
    api.get_match_ids.return_value = []

    needs = {"rank": True, "mastery": True, "stats": True}
    result = fetch_enrichment(api, "p1", "s1", needs)

    assert result.rank_entry is None
    assert result.league_raw_json is None
    assert result.mastery_records is None
    assert result.recent_stats is None


def test_check_enrich_needed_stats_from_db_returns_none(db):
    db.insert_summoner_rank({
        "puuid": "no_stats_p", "summoner_id": "s1", "queue_type": "RANKED_SOLO_5x5",
        "tier": "GOLD", "rank": "II", "league_points": 50,
        "wins": 10, "losses": 5,
        "veteran": 0, "inactive": 0, "fresh_blood": 0, "hot_streak": 0,
    })
    db.insert_champion_mastery_batch([{
        "puuid": "no_stats_p", "champion_id": 1, "mastery_level": 7,
        "mastery_points": 100000, "last_play_time": None,
        "champion_points_until_next_level": None,
    }])

    needs, precomputed = check_enrich_needed(db, "no_stats_p", "s1")
    assert needs["rank"] is False
    assert needs["mastery"] is False
    assert needs["stats"] is True
    assert precomputed is None


def test_write_enrichment_with_opportunistic_matches(db):
    match_row = _make_match("NA1_OPP")
    part_rows = [_make_participant("NA1_OPP", i) for i in range(10)]

    result = EnrichResult(
        puuid="opp_p1",
        summoner_id="s1",
        opportunistic_matches=[(match_row, part_rows, None, None, '{"test": 1}')],
    )

    write_enrichment(db, result)
    assert db.match_exists("NA1_OPP")

    write_enrichment(db, result)
    assert db.get_match_count() == 1


def test_write_enrichment_empty_result(db):
    result = EnrichResult(puuid="empty_p", summoner_id="s1")
    write_enrichment(db, result)
    assert db.get_latest_rank("empty_p") is None
    assert not db.has_mastery_data("empty_p")


def test_concurrent_fetch_enrichment():
    def make_api():
        api = MagicMock()
        api.get_league_by_puuid.return_value = [
            {"queueType": "RANKED_SOLO_5x5", "tier": "GOLD", "rank": "I",
             "leaguePoints": 50, "wins": 30, "losses": 20}
        ]
        api.get_top_masteries.return_value = [
            {"championId": 1, "championLevel": 5, "championPoints": 50000}
        ]
        api.get_match_ids.return_value = []
        return api

    api = make_api()
    needs = {"rank": True, "mastery": True, "stats": True}

    players = [(f"p_{i}", f"s_{i}") for i in range(4)]

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(fetch_enrichment, api, puuid, sid, needs)
            for puuid, sid in players
        ]
        results = [f.result() for f in futures]

    assert len(results) == 4
    for i, r in enumerate(results):
        assert r.puuid == f"p_{i}"
        assert r.rank_entry is not None
        assert r.mastery_records is not None


def test_concurrent_enrichment_with_real_db(test_dsn):
    api = MagicMock()
    api.get_league_by_puuid.return_value = [
        {"queueType": "RANKED_SOLO_5x5", "tier": "SILVER", "rank": "III",
         "leaguePoints": 25, "wins": 15, "losses": 10}
    ]
    api.get_top_masteries.return_value = [
        {"championId": 42, "championLevel": 4, "championPoints": 30000}
    ]
    api.get_match_ids.return_value = []

    needs = {"rank": True, "mastery": True, "stats": True}
    players = [(f"conc_p_{i}", f"conc_s_{i}") for i in range(4)]

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(fetch_enrichment, api, puuid, sid, needs)
            for puuid, sid in players
        ]
        results = [f.result() for f in futures]

    db = MatchDB(test_dsn, fast=True)
    db.begin_batch()
    for r in results:
        write_enrichment(db, r)
    db.end_batch()

    for i in range(4):
        rank = db.get_latest_rank(f"conc_p_{i}")
        assert rank is not None
        assert rank["tier"] == "SILVER"
        assert db.has_mastery_data(f"conc_p_{i}")

    db.close()
