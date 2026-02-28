from lol_genius.features.player import extract_player_features, rank_to_numeric, _bayesian_winrate, compute_tilt_features, PLAYER_FEATURE_NAMES
from lol_genius.features.team import extract_team_features, TEAM_FEATURE_NAMES
from lol_genius.features.draft import extract_draft_features, POSITION_ORDER, DRAFT_FEATURE_NAMES
from lol_genius.features.bans import extract_ban_features, BAN_FEATURE_NAMES


def test_rank_to_numeric():
    assert rank_to_numeric("IRON", "IV", 0) == 0.0
    assert rank_to_numeric("IRON", "I", 0) == 3.0
    assert rank_to_numeric("GOLD", "IV", 50) == 12.5
    assert rank_to_numeric("DIAMOND", "I", 100) == 28.0
    assert rank_to_numeric("CHALLENGER", "I", 500) == 38.0


def test_rank_to_numeric_unknown_tier():
    result = rank_to_numeric("UNKNOWN", "IV", 0)
    assert result == 12.0


def test_bayesian_winrate():
    assert _bayesian_winrate(0, 0) == 0.5
    assert _bayesian_winrate(10, 10) == 0.75
    assert abs(_bayesian_winrate(100, 200) - (105 / 210)) < 1e-9


def test_extract_player_features_full_data():
    participant = {
        "team_position": "MIDDLE",
        "summoner_level": 250,
        "summoner1_id": 4,
        "summoner2_id": 14,
    }
    rank = {
        "tier": "EMERALD", "rank": "II", "league_points": 75,
        "wins": 100, "losses": 80,
        "hot_streak": 1, "fresh_blood": 0, "veteran": 1,
    }
    mastery = {"mastery_points": 50000, "mastery_level": 7, "last_play_time": None}
    recent = {
        "games_played": 20, "wins": 12,
        "avg_kills": 6.0, "avg_deaths": 3.0, "avg_assists": 8.0,
        "avg_cs_per_min": 7.5, "avg_vision": 25.0, "avg_damage_share": 0.28,
        "avg_wards_placed": 10.0, "avg_wards_killed": 3.0,
        "avg_damage_taken": 15000.0, "avg_gold_spent": 12000.0,
        "avg_cc_score": 20.0, "avg_heal_total": 5000.0,
        "avg_magic_dmg_share": 0.4, "avg_phys_dmg_share": 0.5,
        "avg_multikill_rate": 1.5,
    }
    champ_stats = {"games": 10, "wins": 7, "winrate": 0.7}
    role_dist = {"MIDDLE": 15, "TOP": 3, "JUNGLE": 2}

    features = extract_player_features(participant, rank, mastery, recent, champ_stats, role_dist)

    assert set(features.keys()) == set(PLAYER_FEATURE_NAMES)
    assert features["rank_numeric"] == rank_to_numeric("EMERALD", "II", 75)
    assert features["recent_winrate"] == _bayesian_winrate(12, 20)
    assert features["champ_winrate"] == _bayesian_winrate(7, 10)
    assert features["mastery_points"] == 50000.0
    assert features["mastery_points_log"] > 0
    assert features["mastery_above_12k"] == 1.0
    assert features["is_autofill"] == 0.0
    assert features["role_experience_ratio"] == 15 / 20
    assert features["hot_streak"] == 1.0
    assert features["veteran"] == 1.0
    assert features["summoner_level"] == 250.0
    assert features["flash_on_d"] == 1.0
    assert features["has_ignite"] == 1.0
    assert features["avg_wards_placed"] == 10.0
    assert features["avg_multikill_rate"] == 1.5
    assert features["days_since_champ_played"] == 30.0
    assert features["smurf_score"] >= 0


def test_extract_player_features_autofill():
    participant = {"team_position": "JUNGLE"}
    role_dist = {"MIDDLE": 15, "TOP": 3, "JUNGLE": 2}

    features = extract_player_features(participant, None, None, None, None, role_dist)
    assert features["is_autofill"] == 1.0


def test_extract_player_features_no_data():
    features = extract_player_features({"team_position": ""}, None, None, None, None, None)
    assert set(features.keys()) == set(PLAYER_FEATURE_NAMES)
    assert features["rank_numeric"] == 12.0
    assert features["recent_winrate"] == 0.5


def test_spell_features():
    participant = {"team_position": "TOP", "summoner1_id": 12, "summoner2_id": 4}
    features = extract_player_features(participant, None, None, None, None, None)
    assert features["flash_on_d"] == 0.0
    assert features["has_teleport"] == 1.0
    assert features["has_ignite"] == 0.0

    participant2 = {"team_position": "MIDDLE", "summoner1_id": 4, "summoner2_id": 3}
    features2 = extract_player_features(participant2, None, None, None, None, None)
    assert features2["flash_on_d"] == 1.0
    assert features2["has_exhaust"] == 1.0


def test_compute_tilt_features_empty():
    result = compute_tilt_features([])
    assert result["loss_streak"] == 0.0
    assert result["avg_time_between_games_hrs"] == 24.0
    assert result["games_last_24h"] == 0.0


def test_compute_tilt_features_loss_streak():
    outcomes = [
        {"win": False, "game_creation": 1000000, "game_duration": 1800},
        {"win": False, "game_creation": 900000, "game_duration": 1800},
        {"win": True, "game_creation": 800000, "game_duration": 1800},
        {"win": False, "game_creation": 700000, "game_duration": 1800},
    ]
    result = compute_tilt_features(outcomes)
    assert result["loss_streak"] == 2.0


def test_compute_tilt_features_no_losses():
    outcomes = [
        {"win": True, "game_creation": 1000000, "game_duration": 1800},
        {"win": True, "game_creation": 900000, "game_duration": 1800},
    ]
    result = compute_tilt_features(outcomes)
    assert result["loss_streak"] == 0.0


def test_kda_variance_skewness():
    recent = {
        "games_played": 5, "wins": 3,
        "avg_kills": 5.0, "avg_deaths": 3.0, "avg_assists": 7.0,
        "avg_cs_per_min": 7.0, "avg_vision": 20.0, "avg_damage_share": 0.25,
        "avg_wards_placed": 8.0, "avg_wards_killed": 2.0,
        "avg_damage_taken": 12000.0, "avg_gold_spent": 10000.0,
        "avg_cc_score": 15.0, "avg_heal_total": 3000.0,
        "avg_magic_dmg_share": 0.3, "avg_phys_dmg_share": 0.6,
        "avg_multikill_rate": 1.0,
        "kda_per_game": [2.0, 4.0, 6.0, 2.0, 6.0],
    }
    features = extract_player_features({"team_position": "MIDDLE"}, None, None, recent, None, None)
    assert features["kda_variance"] > 0
    assert isinstance(features["kda_skewness"], float)


def test_kda_variance_insufficient_games():
    recent = {
        "games_played": 2, "wins": 1,
        "avg_kills": 5.0, "avg_deaths": 3.0, "avg_assists": 7.0,
        "avg_cs_per_min": 7.0, "avg_vision": 20.0, "avg_damage_share": 0.25,
        "avg_wards_placed": 8.0, "avg_wards_killed": 2.0,
        "avg_damage_taken": 12000.0, "avg_gold_spent": 10000.0,
        "avg_cc_score": 15.0, "avg_heal_total": 3000.0,
        "avg_magic_dmg_share": 0.3, "avg_phys_dmg_share": 0.6,
        "avg_multikill_rate": 1.0,
        "kda_per_game": [3.0, 4.0],
    }
    features = extract_player_features({"team_position": "MIDDLE"}, None, None, recent, None, None)
    assert features["kda_variance"] == 0.0
    assert features["kda_skewness"] == 0.0


def test_extract_team_features():
    player_feats = [
        {"rank_numeric": 20.0, "recent_winrate": 0.55, "mastery_points": 100000, "is_autofill": 0,
         "summoner_level": 200, "hot_streak": 1, "avg_wards_placed": 10, "avg_cc_score": 20},
        {"rank_numeric": 22.0, "recent_winrate": 0.60, "mastery_points": 80000, "is_autofill": 0,
         "summoner_level": 300, "hot_streak": 0, "avg_wards_placed": 12, "avg_cc_score": 15},
        {"rank_numeric": 18.0, "recent_winrate": 0.50, "mastery_points": 120000, "is_autofill": 1,
         "summoner_level": 150, "hot_streak": 1, "avg_wards_placed": 8, "avg_cc_score": 25},
        {"rank_numeric": 21.0, "recent_winrate": 0.52, "mastery_points": 90000, "is_autofill": 0,
         "summoner_level": 250, "hot_streak": 0, "avg_wards_placed": 14, "avg_cc_score": 10},
        {"rank_numeric": 19.0, "recent_winrate": 0.48, "mastery_points": 60000, "is_autofill": 0,
         "summoner_level": 100, "hot_streak": 0, "avg_wards_placed": 20, "avg_cc_score": 30},
    ]
    champ_feats = [
        {"is_ap_champ": 0, "is_mixed_champ": 0, "is_melee": 1, "tag_tank": 1, "tag_assassin": 0, "tag_mage": 0, "tag_marksman": 0, "tag_support": 0,
         "champ_attack_score": 5, "champ_defense_score": 8, "champ_magic_score": 3, "champ_difficulty": 4},
        {"is_ap_champ": 0, "is_mixed_champ": 0, "is_melee": 1, "tag_tank": 0, "tag_assassin": 1, "tag_mage": 0, "tag_marksman": 0, "tag_support": 0,
         "champ_attack_score": 9, "champ_defense_score": 3, "champ_magic_score": 1, "champ_difficulty": 7},
        {"is_ap_champ": 1, "is_mixed_champ": 0, "is_melee": 0, "tag_tank": 0, "tag_assassin": 0, "tag_mage": 1, "tag_marksman": 0, "tag_support": 0,
         "champ_attack_score": 2, "champ_defense_score": 4, "champ_magic_score": 9, "champ_difficulty": 6},
        {"is_ap_champ": 0, "is_mixed_champ": 0, "is_melee": 0, "tag_tank": 0, "tag_assassin": 0, "tag_mage": 0, "tag_marksman": 1, "tag_support": 0,
         "champ_attack_score": 10, "champ_defense_score": 2, "champ_magic_score": 1, "champ_difficulty": 3},
        {"is_ap_champ": 1, "is_mixed_champ": 0, "is_melee": 0, "tag_tank": 0, "tag_assassin": 0, "tag_mage": 0, "tag_marksman": 0, "tag_support": 1,
         "champ_attack_score": 3, "champ_defense_score": 5, "champ_magic_score": 7, "champ_difficulty": 5},
    ]

    features = extract_team_features(player_feats, champ_feats)

    assert set(features.keys()) == set(TEAM_FEATURE_NAMES)
    assert features["avg_rank"] == 20.0
    assert features["ad_ratio"] == 0.6
    assert features["ap_ratio"] == 0.4
    assert features["melee_count"] == 2.0
    assert features["tank_count"] == 1.0
    assert features["autofill_count"] == 1.0
    assert features["avg_summoner_level"] == (200 + 300 + 150 + 250 + 100) / 5
    assert features["hot_streak_count"] == 2.0
    assert features["avg_wards_placed"] == (10 + 12 + 8 + 14 + 20) / 5
    assert features["avg_cc_score"] == (20 + 15 + 25 + 10 + 30) / 5
    assert features["damage_diversity"] > 0
    assert features["total_attack_score"] == 5 + 9 + 2 + 10 + 3
    assert features["total_defense_score"] == 8 + 3 + 4 + 2 + 5


def test_extract_draft_features():
    blue_pf = {
        "TOP": {"rank_numeric": 20.0, "mastery_points": 100000, "recent_winrate": 0.55, "champ_winrate": 0.6, "summoner_level": 200},
        "JUNGLE": {"rank_numeric": 22.0, "mastery_points": 80000, "recent_winrate": 0.60, "champ_winrate": 0.5, "summoner_level": 300},
        "MIDDLE": {"rank_numeric": 18.0, "mastery_points": 120000, "recent_winrate": 0.50, "champ_winrate": 0.55, "summoner_level": 150},
        "BOTTOM": {"rank_numeric": 21.0, "mastery_points": 90000, "recent_winrate": 0.52, "champ_winrate": 0.48, "summoner_level": 250},
        "UTILITY": {"rank_numeric": 19.0, "mastery_points": 60000, "recent_winrate": 0.48, "champ_winrate": 0.52, "summoner_level": 100},
    }
    red_pf = {
        "TOP": {"rank_numeric": 19.0, "mastery_points": 90000, "recent_winrate": 0.50, "champ_winrate": 0.55, "summoner_level": 180},
        "JUNGLE": {"rank_numeric": 21.0, "mastery_points": 70000, "recent_winrate": 0.55, "champ_winrate": 0.52, "summoner_level": 280},
        "MIDDLE": {"rank_numeric": 20.0, "mastery_points": 110000, "recent_winrate": 0.53, "champ_winrate": 0.58, "summoner_level": 200},
        "BOTTOM": {"rank_numeric": 22.0, "mastery_points": 85000, "recent_winrate": 0.58, "champ_winrate": 0.50, "summoner_level": 220},
        "UTILITY": {"rank_numeric": 18.0, "mastery_points": 50000, "recent_winrate": 0.45, "champ_winrate": 0.50, "summoner_level": 90},
    }

    features = extract_draft_features({}, {}, blue_pf, red_pf)

    assert len(features) == len(DRAFT_FEATURE_NAMES)
    assert features["top_rank_diff"] == 1.0
    assert features["jg_rank_diff"] == 1.0
    assert features["mid_rank_diff"] == -2.0
    assert features["sup_rank_diff"] == 1.0
    assert features["top_summoner_level_diff"] == 20.0
    assert features["sup_summoner_level_diff"] == 10.0


def test_ban_features():
    bans = [
        {"match_id": "NA1_1", "team_id": 100, "champion_id": 10, "pick_turn": 1},
        {"match_id": "NA1_1", "team_id": 100, "champion_id": 20, "pick_turn": 2},
        {"match_id": "NA1_1", "team_id": 100, "champion_id": 30, "pick_turn": 3},
        {"match_id": "NA1_1", "team_id": 200, "champion_id": 40, "pick_turn": 4},
        {"match_id": "NA1_1", "team_id": 200, "champion_id": 50, "pick_turn": 5},
    ]
    blue_top_champs = {"p1": [40, 41], "p2": [42]}
    red_top_champs = {"p3": [10, 11], "p4": [99]}

    features = extract_ban_features(bans, blue_top_champs, red_top_champs)

    assert features["blue_bans_count"] == 3.0
    assert features["red_bans_count"] == 2.0
    assert features["blue_target_banned"] == 1.0
    assert features["red_target_banned"] == 1.0


def test_ban_features_empty():
    features = extract_ban_features([], {}, {})
    assert features["blue_bans_count"] == 0.0
    assert features["red_bans_count"] == 0.0
    assert features["blue_target_banned"] == 0.0
    assert features["red_target_banned"] == 0.0
