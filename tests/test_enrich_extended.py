from unittest.mock import MagicMock

from lol_genius.crawler.enrich import (
    _fetch_recent_stats_via_api,
    re_enrich_stale_batch,
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
        "kills": 5,
        "deaths": 3,
        "assists": 7,
        "total_damage": 20000,
        "cs": 180,
        "vision_score": 25,
        "gold_earned": 12000,
        "summoner1_id": 4,
        "summoner2_id": 14,
        "summoner_level": 200,
        "perks_primary_style": 8100,
        "perks_sub_style": 8300,
        "perks_keystone": 8112,
        "perks_offense": 5008,
        "perks_flex": 5008,
        "perks_defense": 5002,
        "magic_damage_to_champions": 8000,
        "physical_damage_to_champions": 10000,
        "true_damage_to_champions": 2000,
        "total_damage_taken": 15000,
        "damage_self_mitigated": 8000,
        "wards_placed": 10,
        "wards_killed": 3,
        "detector_wards_placed": 2,
        "gold_spent": 11000,
        "time_ccing_others": 20,
        "total_heal": 5000,
        "total_heals_on_teammates": 1000,
        "double_kills": 1,
        "triple_kills": 0,
        "quadra_kills": 0,
        "penta_kills": 0,
        "largest_killing_spree": 5,
        "item0": 3071,
        "item1": 3047,
        "item2": 3026,
        "item3": 3053,
        "item4": 3065,
        "item5": 3075,
        "item6": 3340,
        "neutral_minions_killed": 30,
        "total_minions_killed": 150,
        "champion_level": 16,
    }


def _make_match(
    match_id="NA1_123", blue_win=1, game_creation=1700000000000, game_duration=1800
):
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


def _make_riot_match_response(match_id, puuid, win=True, duration=1800):
    participants = []
    for i in range(10):
        p = {
            "puuid": puuid if i == 0 else f"other_{i}",
            "teamId": 100 if i < 5 else 200,
            "win": (win if i == 0 else not win),
            "kills": 8,
            "deaths": 4,
            "assists": 10,
            "totalMinionsKilled": 150,
            "neutralMinionsKilled": 30,
            "visionScore": 30,
            "wardsPlaced": 12,
            "wardsKilled": 5,
            "totalDamageTaken": 18000,
            "goldSpent": 13000,
            "timeCCingOthers": 25,
            "totalHeal": 6000,
            "totalDamageDealtToChampions": 22000,
            "magicDamageDealtToChampions": 10000,
            "physicalDamageDealtToChampions": 10000,
            "trueDamageDealtToChampions": 2000,
            "doubleKills": 2,
            "tripleKills": 1,
            "quadraKills": 0,
            "pentaKills": 0,
            "championId": i + 1,
            "championName": f"Champ{i}",
            "teamPosition": ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"][i % 5],
            "summonerId": f"summ_{i}",
            "summonerLevel": 200,
            "summoner1Id": 4,
            "summoner2Id": 14,
            "perks": {
                "statPerks": {"offense": 5008, "flex": 5008, "defense": 5002},
                "styles": [
                    {"style": 8100, "selections": [{"perk": 8112}]},
                    {"style": 8300},
                ],
            },
            "totalDamageDealt": 25000,
            "goldEarned": 14000,
            "item0": 3071,
            "item1": 3047,
            "item2": 3026,
            "item3": 3053,
            "item4": 3065,
            "item5": 3075,
            "item6": 3340,
            "damageSelfMitigated": 8000,
            "detectorWardsPlaced": 2,
            "totalHealsOnTeammates": 1000,
            "largestKillingSpree": 5,
            "champLevel": 16,
        }
        participants.append(p)

    return {
        "metadata": {
            "matchId": match_id,
            "participants": [p["puuid"] for p in participants],
        },
        "info": {
            "matchId": match_id,
            "gameVersion": "14.10.1",
            "gameDuration": duration,
            "queueId": 420,
            "gameCreation": 1700000000000,
            "gameStartTimestamp": 1700000000000,
            "gameEndTimestamp": 1700000000000 + duration * 1000,
            "platformId": "NA1",
            "participants": participants,
            "teams": [
                {"teamId": 100, "win": True, "bans": [], "objectives": {}},
                {"teamId": 200, "win": False, "bans": [], "objectives": {}},
            ],
        },
    }


class TestFetchRecentStatsViaApi:
    def test_returns_none_on_no_match_ids(self):
        api = MagicMock()
        api.get_match_ids.return_value = []
        result = _fetch_recent_stats_via_api(api, "p1")
        assert result is None

    def test_returns_none_when_no_valid_matches(self):
        api = MagicMock()
        api.get_match_ids.return_value = ["m1", "m2"]
        api.get_match.return_value = None
        result = _fetch_recent_stats_via_api(api, "p1")
        assert result is None

    def test_computes_stats_from_single_match(self):
        api = MagicMock()
        api.get_match_ids.return_value = ["NA1_001"]
        api.get_match.return_value = _make_riot_match_response(
            "NA1_001", "test_p", win=True, duration=1800
        )

        result = _fetch_recent_stats_via_api(api, "test_p")

        assert result is not None
        assert result["puuid"] == "test_p"
        assert result["games_played"] == 1
        assert result["wins"] == 1
        assert result["avg_kills"] == 8.0
        assert result["avg_deaths"] == 4.0
        assert result["avg_assists"] == 10.0
        assert result["avg_vision"] == 30.0
        assert result["avg_wards_placed"] == 12.0
        assert result["avg_wards_killed"] == 5.0
        assert result["kda_per_game"] == [(8 + 10) / 4]

    def test_computes_stats_from_multiple_matches(self):
        api = MagicMock()
        api.get_match_ids.return_value = ["NA1_001", "NA1_002"]
        api.get_match.side_effect = [
            _make_riot_match_response("NA1_001", "multi_p", win=True),
            _make_riot_match_response("NA1_002", "multi_p", win=False),
        ]

        result = _fetch_recent_stats_via_api(api, "multi_p")

        assert result["games_played"] == 2
        assert result["wins"] == 1
        assert result["avg_kills"] == 8.0

    def test_passes_start_time_to_api(self):
        api = MagicMock()
        api.get_match_ids.return_value = []

        _fetch_recent_stats_via_api(api, "p1", start_time=1700000)
        api.get_match_ids.assert_called_once_with(
            "p1", count=20, queue=420, start_time=1700000
        )

    def test_collects_opportunistic_matches(self):
        api = MagicMock()
        api.get_match_ids.return_value = ["NA1_OPP1"]
        api.get_match.return_value = _make_riot_match_response(
            "NA1_OPP1", "opp_p", win=True
        )

        result = _fetch_recent_stats_via_api(api, "opp_p")

        opp = result.get("_opportunistic_matches", [])
        assert len(opp) == 1
        match_row, part_rows, bans, objectives, raw_json = opp[0]
        assert match_row["match_id"] == "NA1_OPP1"

    def test_damage_share_calculation(self):
        api = MagicMock()
        api.get_match_ids.return_value = ["NA1_DMG"]
        api.get_match.return_value = _make_riot_match_response(
            "NA1_DMG", "dmg_p", win=True
        )

        result = _fetch_recent_stats_via_api(api, "dmg_p")

        assert 0 < result["avg_damage_share"] <= 1.0
        assert 0 < result["avg_magic_dmg_share"] <= 1.0
        assert 0 < result["avg_phys_dmg_share"] <= 1.0

    def test_cs_per_min_calculation(self):
        api = MagicMock()
        api.get_match_ids.return_value = ["NA1_CS"]
        api.get_match.return_value = _make_riot_match_response(
            "NA1_CS", "cs_p", duration=600
        )

        result = _fetch_recent_stats_via_api(api, "cs_p")

        expected_cs_per_min = (150 + 30) / 10.0
        assert abs(result["avg_cs_per_min"] - expected_cs_per_min) < 0.01

    def test_skips_match_where_puuid_not_found(self):
        api = MagicMock()
        api.get_match_ids.return_value = ["NA1_MISS"]
        match_data = _make_riot_match_response("NA1_MISS", "someone_else", win=True)
        api.get_match.return_value = match_data

        result = _fetch_recent_stats_via_api(api, "not_in_match")
        assert result is None


class TestReEnrichStaleBatch:
    def test_refreshes_rank_only(self, db):
        api = MagicMock()
        api.get_league_by_puuid.return_value = [
            {
                "queueType": "RANKED_SOLO_5x5",
                "tier": "GOLD",
                "rank": "II",
                "leaguePoints": 50,
                "wins": 30,
                "losses": 20,
            }
        ]

        stale = [{"puuid": "stale_p1", "summoner_id": "s1"}]
        count = re_enrich_stale_batch(api, db, stale)

        assert count == 1
        api.get_league_by_puuid.assert_called_once_with("stale_p1")
        api.get_top_masteries.assert_not_called()
        api.get_match_ids.assert_not_called()

        rank = db.get_latest_rank("stale_p1")
        assert rank is not None
        assert rank["tier"] == "GOLD"

    def test_refreshes_multiple_entries(self, db):
        api = MagicMock()
        api.get_league_by_puuid.return_value = [
            {
                "queueType": "RANKED_SOLO_5x5",
                "tier": "SILVER",
                "rank": "I",
                "leaguePoints": 75,
                "wins": 40,
                "losses": 30,
            }
        ]

        stale = [
            {"puuid": "batch_p1", "summoner_id": "s1"},
            {"puuid": "batch_p2", "summoner_id": "s2"},
            {"puuid": "batch_p3"},
        ]
        count = re_enrich_stale_batch(api, db, stale)

        assert count == 3
        assert api.get_league_by_puuid.call_count == 3

    def test_recomputes_stats_from_db(self, db):
        match = _make_match("NA1_STALE")
        participants = [
            _make_participant(
                "NA1_STALE", i, puuid="stat_p" if i == 0 else f"filler_{i}"
            )
            for i in range(10)
        ]
        db.insert_match(match, participants)

        api = MagicMock()
        api.get_league_by_puuid.return_value = []

        stale = [{"puuid": "stat_p", "summoner_id": "s1"}]
        count = re_enrich_stale_batch(api, db, stale)
        assert count == 1

    def test_missing_summoner_id_defaults_empty(self, db):
        api = MagicMock()
        api.get_league_by_puuid.return_value = [
            {
                "queueType": "RANKED_SOLO_5x5",
                "tier": "BRONZE",
                "rank": "III",
                "leaguePoints": 10,
                "wins": 5,
                "losses": 5,
            }
        ]

        stale = [{"puuid": "no_sid_p"}]
        count = re_enrich_stale_batch(api, db, stale)
        assert count == 1

        rank = db.get_latest_rank("no_sid_p")
        assert rank is not None
