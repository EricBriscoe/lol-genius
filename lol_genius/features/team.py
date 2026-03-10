from __future__ import annotations

import math


def extract_team_features(
    player_features: list[dict],
    champion_features: list[dict],
) -> dict:
    features: dict[str, float] = {}

    ranks = [pf.get("rank_numeric", 12.0) for pf in player_features]
    features["avg_rank"] = sum(ranks) / max(len(ranks), 1)
    if len(ranks) > 1:
        mean = features["avg_rank"]
        features["rank_spread"] = math.sqrt(sum((r - mean) ** 2 for r in ranks) / len(ranks))
    else:
        features["rank_spread"] = 0.0

    winrates = [pf.get("recent_winrate", 0.5) for pf in player_features]
    features["avg_team_winrate"] = sum(winrates) / max(len(winrates), 1)

    masteries = [pf.get("mastery_points", 0) for pf in player_features]
    features["avg_mastery"] = sum(masteries) / max(len(masteries), 1)

    ad_count = sum(
        1
        for cf in champion_features
        if cf.get("is_ap_champ", 0) < 0.5 and cf.get("is_mixed_champ", 0) < 0.5
    )
    ap_count = sum(1 for cf in champion_features if cf.get("is_ap_champ", 0) > 0.5)
    mixed_count = sum(1 for cf in champion_features if cf.get("is_mixed_champ", 0) > 0.5)
    total = max(len(champion_features), 1)
    features["ad_ratio"] = ad_count / total
    features["ap_ratio"] = ap_count / total
    ratios = [ad_count / total, ap_count / total, mixed_count / total]
    features["damage_diversity"] = -sum(r * math.log2(r) for r in ratios if r > 0)

    features["melee_count"] = float(
        sum(1 for cf in champion_features if cf.get("is_melee", 0) > 0.5)
    )

    features["tank_count"] = float(
        sum(1 for cf in champion_features if cf.get("tag_tank", 0) > 0.5)
    )
    features["assassin_count"] = float(
        sum(1 for cf in champion_features if cf.get("tag_assassin", 0) > 0.5)
    )
    features["mage_count"] = float(
        sum(1 for cf in champion_features if cf.get("tag_mage", 0) > 0.5)
    )
    features["marksman_count"] = float(
        sum(1 for cf in champion_features if cf.get("tag_marksman", 0) > 0.5)
    )
    features["support_count"] = float(
        sum(1 for cf in champion_features if cf.get("tag_support", 0) > 0.5)
    )

    autofill_count = sum(1 for pf in player_features if pf.get("is_autofill", 0) > 0.5)
    features["autofill_count"] = float(autofill_count)

    levels = [pf.get("summoner_level", 0) for pf in player_features]
    features["avg_summoner_level"] = sum(levels) / max(len(levels), 1)

    features["hot_streak_count"] = float(
        sum(1 for pf in player_features if pf.get("hot_streak", 0) > 0.5)
    )

    wards = [pf.get("avg_wards_placed", 0) for pf in player_features]
    features["avg_wards_placed"] = sum(wards) / max(len(wards), 1)

    cc = [pf.get("avg_cc_score", 0) for pf in player_features]
    features["avg_cc_score"] = sum(cc) / max(len(cc), 1)

    n_champs = max(len(champion_features), 1)
    features["total_attack_score"] = sum(
        cf.get("champ_attack_score", 5) for cf in champion_features
    )
    features["total_defense_score"] = sum(
        cf.get("champ_defense_score", 5) for cf in champion_features
    )
    features["total_magic_score"] = sum(cf.get("champ_magic_score", 5) for cf in champion_features)
    features["avg_difficulty"] = (
        sum(cf.get("champ_difficulty", 5) for cf in champion_features) / n_champs
    )

    return features


TEAM_FEATURE_NAMES = [
    "avg_rank",
    "rank_spread",
    "avg_team_winrate",
    "avg_mastery",
    "ad_ratio",
    "ap_ratio",
    "melee_count",
    "tank_count",
    "assassin_count",
    "mage_count",
    "marksman_count",
    "support_count",
    "autofill_count",
    "damage_diversity",
    "avg_summoner_level",
    "hot_streak_count",
    "avg_wards_placed",
    "avg_cc_score",
    "total_attack_score",
    "total_defense_score",
    "total_magic_score",
    "avg_difficulty",
]
