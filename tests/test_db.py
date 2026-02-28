import json

import psycopg2
import psycopg2.extras
import pytest

from lol_genius.db.connection import get_connection, get_connection_fast, init_db
from lol_genius.db.queries import MatchDB


def _make_participant(match_id, i, puuid=None, team_id=None, win=None,
                      kills=5, deaths=3, assists=7, total_damage=20000,
                      cs=180, vision_score=25, gold_earned=12000,
                      wards_placed=10, wards_killed=3, total_damage_taken=15000,
                      gold_spent=11000, time_ccing_others=20, total_heal=5000,
                      magic_damage_to_champions=8000, physical_damage_to_champions=10000,
                      double_kills=1, triple_kills=0, quadra_kills=0, penta_kills=0):
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
        "kills": kills, "deaths": deaths, "assists": assists,
        "total_damage": total_damage, "cs": cs,
        "vision_score": vision_score, "gold_earned": gold_earned,
        "summoner1_id": 4, "summoner2_id": 14,
        "summoner_level": 200,
        "perks_primary_style": 8100, "perks_sub_style": 8300,
        "perks_keystone": 8112, "perks_offense": 5008, "perks_flex": 5008, "perks_defense": 5002,
        "magic_damage_to_champions": magic_damage_to_champions,
        "physical_damage_to_champions": physical_damage_to_champions,
        "true_damage_to_champions": 2000,
        "total_damage_taken": total_damage_taken,
        "damage_self_mitigated": 8000,
        "wards_placed": wards_placed, "wards_killed": wards_killed,
        "detector_wards_placed": 2,
        "gold_spent": gold_spent,
        "time_ccing_others": time_ccing_others,
        "total_heal": total_heal,
        "total_heals_on_teammates": 1000,
        "double_kills": double_kills, "triple_kills": triple_kills,
        "quadra_kills": quadra_kills, "penta_kills": penta_kills,
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


def test_init_db(test_dsn):
    conn = get_connection(test_dsn)
    cur = conn.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    table_names = {t["table_name"] for t in cur.fetchall()}
    assert "matches" in table_names
    assert "participants" in table_names
    assert "summoner_ranks" in table_names
    assert "crawl_queue" in table_names
    assert "match_raw_json" in table_names
    assert "match_bans" in table_names
    assert "match_team_objectives" in table_names
    assert "league_raw_json" in table_names
    assert "mastery_raw_json" in table_names
    conn.close()


def test_insert_and_query_match(db):
    match = _make_match()
    participants = [_make_participant("NA1_123", i) for i in range(10)]

    db.insert_match(match, participants)

    assert db.match_exists("NA1_123")
    assert not db.match_exists("NA1_456")
    assert db.get_match_count() == 1

    result = db.get_match("NA1_123")
    assert result["blue_win"] == 1
    assert result["platform_id"] == "NA1"

    parts = db.get_participants_for_match("NA1_123")
    assert len(parts) == 10
    assert parts[0]["summoner1_id"] == 4
    assert parts[0]["perks_keystone"] == 8112
    assert parts[0]["wards_placed"] == 10


def test_insert_match_with_bans_and_objectives(db):
    match = _make_match()
    participants = [_make_participant("NA1_123", i) for i in range(10)]
    bans = [
        {"match_id": "NA1_123", "team_id": 100, "champion_id": 1, "pick_turn": 1},
        {"match_id": "NA1_123", "team_id": 100, "champion_id": 2, "pick_turn": 2},
        {"match_id": "NA1_123", "team_id": 200, "champion_id": 3, "pick_turn": 3},
    ]
    objectives = [
        {"match_id": "NA1_123", "team_id": 100, "objective": "baron", "first": 1, "kills": 2},
        {"match_id": "NA1_123", "team_id": 200, "objective": "dragon", "first": 1, "kills": 3},
    ]

    db.insert_match(match, participants, bans=bans, objectives=objectives, raw_json='{"test": 1}')

    result_bans = db.get_match_bans("NA1_123")
    assert len(result_bans) == 3
    assert result_bans[0]["champion_id"] in (1, 2, 3)

    raw_row = db._execute("SELECT * FROM match_raw_json WHERE match_id = %s", ("NA1_123",)).fetchone()
    assert raw_row is not None
    assert json.loads(raw_row["raw_json"]) == {"test": 1}

    obj_rows = db._execute("SELECT * FROM match_team_objectives WHERE match_id = %s", ("NA1_123",)).fetchall()
    assert len(obj_rows) == 2


def test_crawl_queue(db):
    puuids = ["p1", "p2", "p3"]
    added = db.add_puuids_to_queue(puuids)
    assert added == 3

    added_again = db.add_puuids_to_queue(["p2", "p4"])
    assert added_again == 1

    pending = db.get_pending_puuids(limit=10)
    assert len(pending) == 4

    db.mark_puuid_processing("p1")
    pending = db.get_pending_puuids(limit=10)
    assert "p1" not in pending

    db.mark_puuid_done("p1")
    stats = db.get_queue_stats()
    assert stats.get("done", 0) == 1


def test_get_pending_puuids_tier_weights(db):
    db.add_puuids_to_queue(["d1", "d2", "d3"], tier="DIAMOND")
    db.add_puuids_to_queue(["g1", "g2"], tier="GOLD")
    db.add_puuids_to_queue(["i1"], tier="IRON")

    tier_weights = {"IRON": 5, "GOLD": 50, "DIAMOND": 200}
    result = db.get_pending_puuids(limit=6, tier_weights=tier_weights)

    assert len(result) == 6
    iron_idx = result.index("i1")
    gold_idxs = [result.index(p) for p in ["g1", "g2"]]
    diamond_idxs = [result.index(p) for p in ["d1", "d2", "d3"]]
    assert iron_idx < min(gold_idxs)
    assert min(gold_idxs) < min(diamond_idxs)


def test_summoner_rank(db):
    rank = {
        "puuid": "p1",
        "summoner_id": "s1",
        "queue_type": "RANKED_SOLO_5x5",
        "tier": "DIAMOND",
        "rank": "III",
        "league_points": 42,
        "wins": 100,
        "losses": 90,
        "veteran": 1,
        "inactive": 0,
        "fresh_blood": 0,
        "hot_streak": 1,
    }
    db.insert_summoner_rank(rank)

    result = db.get_latest_rank("p1")
    assert result["tier"] == "DIAMOND"
    assert result["league_points"] == 42
    assert result["veteran"] == 1
    assert result["hot_streak"] == 1


def test_champion_mastery_expanded(db):
    records = [{
        "puuid": "p1",
        "champion_id": 1,
        "mastery_level": 7,
        "mastery_points": 100000,
        "last_play_time": 1700000000000,
        "champion_points_until_next_level": 0,
    }]
    db.insert_champion_mastery_batch(records)

    result = db.get_champion_mastery_record("p1", 1)
    assert result["last_play_time"] == 1700000000000
    assert result["champion_points_until_next_level"] == 0


def _insert_match_with_stats(db, match_id, game_creation, puuid, team_id, win, kills, deaths, assists, total_damage, cs, vision_score, game_duration,
                             wards_placed=10, wards_killed=3, total_damage_taken=15000, gold_spent=11000,
                             time_ccing_others=20, total_heal=5000,
                             magic_damage_to_champions=8000, physical_damage_to_champions=10000,
                             double_kills=1, triple_kills=0, quadra_kills=0, penta_kills=0):
    match = _make_match(match_id=match_id, blue_win=1 if (team_id == 100 and win) else 0,
                        game_creation=game_creation, game_duration=game_duration)
    participants = []
    for i in range(10):
        is_target = i == 0
        tid = team_id if is_target else (100 if i < 5 else 200)
        participants.append(_make_participant(
            match_id, i,
            puuid=puuid if is_target else f"filler_{match_id}_{i}",
            team_id=tid,
            win=win if is_target else (1 if i < 5 else 0),
            kills=kills if is_target else 3,
            deaths=deaths if is_target else 2,
            assists=assists if is_target else 4,
            total_damage=total_damage if is_target else 10000,
            cs=cs if is_target else 150,
            vision_score=vision_score if is_target else 20,
            wards_placed=wards_placed if is_target else 5,
            wards_killed=wards_killed if is_target else 1,
            total_damage_taken=total_damage_taken if is_target else 12000,
            gold_spent=gold_spent if is_target else 10000,
            time_ccing_others=time_ccing_others if is_target else 10,
            total_heal=total_heal if is_target else 3000,
            magic_damage_to_champions=magic_damage_to_champions if is_target else 4000,
            physical_damage_to_champions=physical_damage_to_champions if is_target else 5000,
            double_kills=double_kills if is_target else 0,
            triple_kills=triple_kills if is_target else 0,
            quadra_kills=quadra_kills if is_target else 0,
            penta_kills=penta_kills if is_target else 0,
        ))
    db.insert_match(match, participants)


def test_compute_recent_stats_from_db(db):
    puuid = "test_player"

    _insert_match_with_stats(
        db, "NA1_A", 1700000000000, puuid, team_id=100,
        win=1, kills=10, deaths=2, assists=8, total_damage=25000,
        cs=200, vision_score=30, game_duration=1800,
        wards_placed=12, wards_killed=4, total_damage_taken=18000, gold_spent=13000,
        time_ccing_others=25, total_heal=6000, magic_damage_to_champions=10000,
        physical_damage_to_champions=12000, double_kills=2, triple_kills=1,
    )
    _insert_match_with_stats(
        db, "NA1_B", 1700000100000, puuid, team_id=100,
        win=0, kills=4, deaths=6, assists=10, total_damage=15000,
        cs=160, vision_score=20, game_duration=1200,
        wards_placed=8, wards_killed=2, total_damage_taken=20000, gold_spent=10000,
        time_ccing_others=15, total_heal=4000, magic_damage_to_champions=6000,
        physical_damage_to_champions=7000, double_kills=0,
    )
    _insert_match_with_stats(
        db, "NA1_C", 1700000200000, puuid, team_id=200,
        win=1, kills=8, deaths=4, assists=6, total_damage=20000,
        cs=180, vision_score=25, game_duration=1500,
        wards_placed=10, wards_killed=3, total_damage_taken=16000, gold_spent=12000,
        time_ccing_others=20, total_heal=5000, magic_damage_to_champions=8000,
        physical_damage_to_champions=10000, double_kills=0,
    )

    stats = db.compute_recent_stats_from_db(puuid)
    assert stats is not None
    assert stats["games_played"] == 3
    assert stats["wins"] == 2
    assert stats["avg_kills"] == pytest.approx((10 + 4 + 8) / 3)
    assert stats["avg_deaths"] == pytest.approx((2 + 6 + 4) / 3)
    assert stats["avg_assists"] == pytest.approx((8 + 10 + 6) / 3)
    assert stats["avg_cs_per_min"] == pytest.approx(
        (200 / 30 + 160 / 20 + 180 / 25) / 3
    )
    assert stats["avg_vision"] == pytest.approx((30 + 20 + 25) / 3)
    assert stats["avg_damage_share"] > 0
    assert stats["avg_wards_placed"] == pytest.approx((12 + 8 + 10) / 3)
    assert stats["avg_wards_killed"] == pytest.approx((4 + 2 + 3) / 3)
    assert stats["avg_damage_taken"] == pytest.approx((18000 + 20000 + 16000) / 3)
    assert stats["avg_gold_spent"] == pytest.approx((13000 + 10000 + 12000) / 3)
    assert stats["avg_cc_score"] == pytest.approx((25 + 15 + 20) / 3)
    assert stats["avg_heal_total"] == pytest.approx((6000 + 4000 + 5000) / 3)
    assert stats["avg_multikill_rate"] == pytest.approx((2 + 1 + 0 + 0) / 3)


def test_compute_recent_stats_start_time_filter(db):
    puuid = "filter_player"

    _insert_match_with_stats(
        db, "NA1_OLD", 1600000000000, puuid, team_id=100,
        win=1, kills=10, deaths=2, assists=8, total_damage=20000,
        cs=200, vision_score=30, game_duration=1800,
    )
    _insert_match_with_stats(
        db, "NA1_NEW", 1700000000000, puuid, team_id=100,
        win=0, kills=4, deaths=6, assists=10, total_damage=15000,
        cs=160, vision_score=20, game_duration=1200,
    )

    stats_all = db.compute_recent_stats_from_db(puuid)
    assert stats_all["games_played"] == 2

    stats_filtered = db.compute_recent_stats_from_db(puuid, start_time_ms=1650000000000)
    assert stats_filtered["games_played"] == 1
    assert stats_filtered["avg_kills"] == pytest.approx(4.0)


def test_raw_json_tables(db):
    db.insert_match_raw_json("NA1_999", '{"metadata": {}}')
    row = db._execute("SELECT * FROM match_raw_json WHERE match_id = %s", ("NA1_999",)).fetchone()
    assert row["raw_json"] == '{"metadata": {}}'

    db.insert_league_raw_json("p1", '[{"tier": "GOLD"}]')
    row = db._execute("SELECT * FROM league_raw_json WHERE puuid = %s", ("p1",)).fetchone()
    assert "GOLD" in row["raw_json"]

    db.insert_mastery_raw_json("p1", 1, '{"championId": 1}')
    row = db._execute("SELECT * FROM mastery_raw_json WHERE puuid = %s AND champion_id = %s", ("p1", 1)).fetchone()
    assert row is not None


def test_get_player_top_champions(db):
    records = [
        {"puuid": "p1", "champion_id": 10, "mastery_level": 7, "mastery_points": 200000, "last_play_time": None, "champion_points_until_next_level": None},
        {"puuid": "p1", "champion_id": 20, "mastery_level": 5, "mastery_points": 50000, "last_play_time": None, "champion_points_until_next_level": None},
        {"puuid": "p1", "champion_id": 30, "mastery_level": 6, "mastery_points": 100000, "last_play_time": None, "champion_points_until_next_level": None},
    ]
    db.insert_champion_mastery_batch(records)

    top = db.get_player_top_champions("p1", limit=2)
    assert len(top) == 2
    assert top[0] == 10
    assert top[1] == 30


def test_has_mastery_data(db):
    assert db.has_mastery_data("p1") is False

    db.insert_champion_mastery_batch([{
        "puuid": "p1",
        "champion_id": 1,
        "mastery_level": 7,
        "mastery_points": 100000,
        "last_play_time": 1700000000000,
        "champion_points_until_next_level": 0,
    }])

    assert db.has_mastery_data("p1") is True
    assert db.has_mastery_data("unknown_puuid") is False


def test_fast_connection(test_dsn):
    db = MatchDB(test_dsn, fast=True)
    db.get_match_count()
    db.close()

    db2 = MatchDB(test_dsn, fast=True)
    db2.get_match_count()
    db2.close()


def test_batch_mode_defers_commit(test_dsn, db):
    db.begin_batch()

    rank = {
        "puuid": "batch_p1",
        "summoner_id": "s1",
        "queue_type": "RANKED_SOLO_5x5",
        "tier": "GOLD",
        "rank": "II",
        "league_points": 50,
        "wins": 10,
        "losses": 5,
        "veteran": 0,
        "inactive": 0,
        "fresh_blood": 0,
        "hot_streak": 0,
    }
    db.insert_summoner_rank(rank)

    result = db.get_latest_rank("batch_p1")
    assert result is not None
    assert result["tier"] == "GOLD"

    db.end_batch()

    db2 = MatchDB(test_dsn, fast=True)
    result2 = db2.get_latest_rank("batch_p1")
    assert result2 is not None
    assert result2["tier"] == "GOLD"
    db2.close()


def test_flush_persists_in_batch(test_dsn, db):
    db.begin_batch()

    db.add_puuids_to_queue(["flush_p1", "flush_p2"])
    db.flush()

    db.end_batch()

    db2 = MatchDB(test_dsn, fast=True)
    pending = db2.get_pending_puuids(limit=10)
    assert "flush_p1" in pending
    assert "flush_p2" in pending
    db2.close()


def test_maybe_commit_auto_in_non_batch(test_dsn, db):
    assert db._batch_mode is False

    db.add_puuids_to_queue(["auto_p1"])

    db2 = MatchDB(test_dsn, fast=True)
    pending = db2.get_pending_puuids(limit=10)
    assert "auto_p1" in pending
    db2.close()


def test_batch_insert_match(test_dsn, db):
    db.begin_batch()

    match = _make_match("NA1_BATCH")
    participants = [_make_participant("NA1_BATCH", i) for i in range(10)]
    db.insert_match(match, participants)
    db.flush()

    assert db.match_exists("NA1_BATCH")
    assert db.get_match_count() == 1

    db.end_batch()
