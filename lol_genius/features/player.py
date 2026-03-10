from __future__ import annotations

import math
import time

TIER_MAP = {
    "IRON": 0,
    "BRONZE": 4,
    "SILVER": 8,
    "GOLD": 12,
    "PLATINUM": 16,
    "EMERALD": 20,
    "DIAMOND": 24,
    "MASTER": 28,
    "GRANDMASTER": 29,
    "CHALLENGER": 30,
}

DIV_MAP = {"IV": 0, "III": 1, "II": 2, "I": 3}

SMURF_WR_RESIDUAL_WEIGHT = 2.0
SMURF_RANK_MISMATCH_WEIGHT = 0.5
SMURF_GAMES_PER_LEVEL_WEIGHT = 1.5
SMURF_RANK_PER_GAME_WEIGHT = 1.0

FLASH_ID = 4
SPELL_MAP = {
    14: "has_ignite",
    12: "has_teleport",
    11: "has_smite",
    3: "has_exhaust",
    7: "has_heal",
    21: "has_barrier",
    6: "has_ghost",
    1: "has_cleanse",
}


def rank_to_numeric(tier: str, division: str, lp: int) -> float:
    base = TIER_MAP.get(tier, 12)
    div_offset = DIV_MAP.get(division, 0)
    return base + div_offset + (lp / 100.0)


def _bayesian_winrate(
    wins: int, games: int, prior_wr: float = 0.5, prior_strength: float = 10.0
) -> float:
    return (wins + prior_strength * prior_wr) / (games + prior_strength)


def extract_player_features(
    participant: dict,
    rank: dict | None,
    mastery: dict | None,
    recent_stats: dict | None,
    champ_stats: dict | None,
    role_dist: dict[str, int] | None,
) -> dict:
    features: dict[str, float] = {}

    if rank:
        features["rank_numeric"] = rank_to_numeric(
            rank.get("tier", "GOLD"),
            rank.get("rank", "IV"),
            rank.get("league_points", 0),
        )
        features["league_points"] = float(rank.get("league_points", 0))
        total_games = rank.get("wins", 0) + rank.get("losses", 0)
        features["ranked_winrate"] = _bayesian_winrate(rank.get("wins", 0), total_games)
        features["ranked_games"] = float(total_games)
        features["hot_streak"] = float(rank.get("hot_streak", 0) or 0)
        features["fresh_blood"] = float(rank.get("fresh_blood", 0) or 0)
        features["veteran"] = float(rank.get("veteran", 0) or 0)
    else:
        features["rank_numeric"] = 12.0
        features["league_points"] = 0.0
        features["ranked_winrate"] = 0.5
        features["ranked_games"] = 0.0
        features["hot_streak"] = 0.0
        features["fresh_blood"] = 0.0
        features["veteran"] = 0.0

    if recent_stats:
        games = max(recent_stats.get("games_played", 1), 1)
        features["recent_winrate"] = _bayesian_winrate(recent_stats.get("wins", 0), games)
        features["recent_games"] = float(games)
        features["avg_kda"] = (
            recent_stats.get("avg_kills", 0) + recent_stats.get("avg_assists", 0)
        ) / max(recent_stats.get("avg_deaths", 1), 1.0)
        features["avg_cs_per_min"] = float(recent_stats.get("avg_cs_per_min", 0) or 0)
        features["avg_vision"] = float(recent_stats.get("avg_vision", 0) or 0)
        features["avg_damage_share"] = float(recent_stats.get("avg_damage_share", 0) or 0)
        features["avg_wards_placed"] = float(recent_stats.get("avg_wards_placed", 0) or 0)
        features["avg_wards_killed"] = float(recent_stats.get("avg_wards_killed", 0) or 0)
        features["avg_damage_taken"] = float(recent_stats.get("avg_damage_taken", 0) or 0)
        features["avg_gold_spent"] = float(recent_stats.get("avg_gold_spent", 0) or 0)
        features["avg_cc_score"] = float(recent_stats.get("avg_cc_score", 0) or 0)
        features["avg_heal_total"] = float(recent_stats.get("avg_heal_total", 0) or 0)
        features["avg_magic_dmg_share"] = float(recent_stats.get("avg_magic_dmg_share", 0) or 0)
        features["avg_phys_dmg_share"] = float(recent_stats.get("avg_phys_dmg_share", 0) or 0)
        features["avg_multikill_rate"] = float(recent_stats.get("avg_multikill_rate", 0) or 0)

        kda_list = recent_stats.get("kda_per_game", [])
        if len(kda_list) >= 3:
            mean_kda = sum(kda_list) / len(kda_list)
            var = sum((k - mean_kda) ** 2 for k in kda_list) / len(kda_list)
            features["kda_variance"] = var
            features["kda_skewness"] = (
                (sum((k - mean_kda) ** 3 for k in kda_list) / len(kda_list)) / (var**1.5)
                if var > 1e-8
                else 0.0
            )
        else:
            features["kda_variance"] = 0.0
            features["kda_skewness"] = 0.0
    else:
        features["recent_winrate"] = 0.5
        features["recent_games"] = 0.0
        features["avg_kda"] = 2.0
        features["avg_cs_per_min"] = 6.0
        features["avg_vision"] = 20.0
        features["avg_damage_share"] = 0.2
        features["avg_wards_placed"] = 0.0
        features["avg_wards_killed"] = 0.0
        features["avg_damage_taken"] = 0.0
        features["avg_gold_spent"] = 0.0
        features["avg_cc_score"] = 0.0
        features["avg_heal_total"] = 0.0
        features["avg_magic_dmg_share"] = 0.0
        features["avg_phys_dmg_share"] = 0.0
        features["avg_multikill_rate"] = 0.0
        features["kda_variance"] = 0.0
        features["kda_skewness"] = 0.0

    if champ_stats and champ_stats.get("games", 0) > 0:
        features["champ_winrate"] = _bayesian_winrate(champ_stats["wins"], champ_stats["games"])
        features["champ_games"] = float(champ_stats["games"])
    else:
        features["champ_winrate"] = 0.5
        features["champ_games"] = 0.0
    features["champ_global_wr"] = 0.5

    features["loss_streak"] = 0.0
    features["avg_time_between_games_hrs"] = 24.0
    features["games_last_24h"] = 0.0

    if mastery:
        raw_pts = float(mastery.get("mastery_points", 0))
        features["mastery_points"] = raw_pts
        features["mastery_points_log"] = math.log1p(raw_pts)
        features["mastery_above_12k"] = 1.0 if raw_pts > 12000 else 0.0
        features["mastery_level"] = float(mastery.get("mastery_level", 0))
        lpt = mastery.get("last_play_time")
        if lpt and lpt > 0:
            now_ms = int(time.time() * 1000)
            features["days_since_champ_played"] = max((now_ms - lpt) / 86400000.0, 0.0)
        else:
            features["days_since_champ_played"] = 30.0
    else:
        features["mastery_points"] = 0.0
        features["mastery_points_log"] = 0.0
        features["mastery_above_12k"] = 0.0
        features["mastery_level"] = 0.0
        features["days_since_champ_played"] = 30.0

    position = participant.get("team_position", "")
    if role_dist and position:
        total_role_games = sum(role_dist.values())
        if total_role_games > 0:
            most_played = max(role_dist, key=role_dist.get)
            features["is_autofill"] = 0.0 if most_played == position else 1.0
            features["role_experience_ratio"] = role_dist.get(position, 0) / total_role_games
        else:
            features["is_autofill"] = 0.0
            features["role_experience_ratio"] = 0.0
    else:
        features["is_autofill"] = 0.0
        features["role_experience_ratio"] = 0.0

    features["summoner_level"] = float(participant.get("summoner_level", 0) or 0)

    rn = features["rank_numeric"]
    wr = features["ranked_winrate"]
    rg = features["ranked_games"]
    sl = features["summoner_level"]

    expected_wr = 0.45 + (rn / 30.0) * 0.1
    features["winrate_rank_residual"] = wr - expected_wr
    features["games_per_level"] = rg / max(sl, 1.0)
    features["rank_per_game"] = rn / max(rg, 1.0)
    expected_rank = min((sl / 500.0) * 30.0, 30.0)
    features["level_rank_mismatch"] = rn - expected_rank

    features["smurf_score"] = (
        max(features["winrate_rank_residual"], 0) * SMURF_WR_RESIDUAL_WEIGHT
        + max(features["level_rank_mismatch"], 0) * SMURF_RANK_MISMATCH_WEIGHT
        + min(features["games_per_level"], 1.0) * SMURF_GAMES_PER_LEVEL_WEIGHT
        + min(features["rank_per_game"], 1.0) * SMURF_RANK_PER_GAME_WEIGHT
    )

    s1 = participant.get("summoner1_id", 0) or 0
    s2 = participant.get("summoner2_id", 0) or 0
    features["flash_on_d"] = 1.0 if s1 == FLASH_ID else 0.0

    for spell_id, feat_name in SPELL_MAP.items():
        features[feat_name] = 1.0 if s1 == spell_id or s2 == spell_id else 0.0

    return features


def compute_tilt_features(recent_outcomes: list[dict]) -> dict[str, float]:
    if not recent_outcomes:
        return {
            "loss_streak": 0.0,
            "avg_time_between_games_hrs": 24.0,
            "games_last_24h": 0.0,
        }

    streak = 0
    for r in recent_outcomes:
        if not r["win"]:
            streak += 1
        else:
            break

    gaps = []
    for i in range(len(recent_outcomes) - 1):
        end_prev = recent_outcomes[i + 1]["game_creation"] + (
            recent_outcomes[i + 1]["game_duration"] * 1000
        )
        gap_ms = recent_outcomes[i]["game_creation"] - end_prev
        if gap_ms > 0:
            gaps.append(gap_ms / 3600000.0)

    latest = recent_outcomes[0]["game_creation"]
    cutoff = latest - 86400000

    return {
        "loss_streak": float(streak),
        "avg_time_between_games_hrs": sum(gaps) / len(gaps) if gaps else 24.0,
        "games_last_24h": float(sum(1 for r in recent_outcomes if r["game_creation"] > cutoff)),
    }


PLAYER_FEATURE_NAMES = [
    "rank_numeric",
    "league_points",
    "ranked_winrate",
    "ranked_games",
    "hot_streak",
    "fresh_blood",
    "veteran",
    "recent_winrate",
    "recent_games",
    "avg_kda",
    "avg_cs_per_min",
    "avg_vision",
    "avg_damage_share",
    "avg_wards_placed",
    "avg_wards_killed",
    "avg_damage_taken",
    "avg_gold_spent",
    "avg_cc_score",
    "avg_heal_total",
    "avg_magic_dmg_share",
    "avg_phys_dmg_share",
    "avg_multikill_rate",
    "kda_variance",
    "kda_skewness",
    "champ_winrate",
    "champ_games",
    "champ_global_wr",
    "mastery_points",
    "mastery_points_log",
    "mastery_above_12k",
    "mastery_level",
    "days_since_champ_played",
    "is_autofill",
    "role_experience_ratio",
    "summoner_level",
    "winrate_rank_residual",
    "games_per_level",
    "rank_per_game",
    "level_rank_mismatch",
    "smurf_score",
    "loss_streak",
    "avg_time_between_games_hrs",
    "games_last_24h",
    "flash_on_d",
    "has_ignite",
    "has_teleport",
    "has_smite",
    "has_exhaust",
    "has_heal",
    "has_barrier",
    "has_ghost",
    "has_cleanse",
]
