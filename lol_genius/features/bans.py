from __future__ import annotations


def extract_ban_features(
    bans: list[dict],
    blue_top_champs: dict[str, list[int]],
    red_top_champs: dict[str, list[int]],
) -> dict:
    features: dict[str, float] = {}

    blue_bans = [b for b in bans if b.get("team_id") == 100]
    red_bans = [b for b in bans if b.get("team_id") == 200]

    features["blue_bans_count"] = float(len(blue_bans))
    features["red_bans_count"] = float(len(red_bans))

    blue_banned_ids = {b["champion_id"] for b in blue_bans if b.get("champion_id", 0) > 0}
    red_banned_ids = {b["champion_id"] for b in red_bans if b.get("champion_id", 0) > 0}

    blue_target_count = 0
    for puuid, champ_ids in red_top_champs.items():
        for cid in champ_ids:
            if cid in blue_banned_ids:
                blue_target_count += 1
                break

    red_target_count = 0
    for puuid, champ_ids in blue_top_champs.items():
        for cid in champ_ids:
            if cid in red_banned_ids:
                red_target_count += 1
                break

    features["blue_target_banned"] = float(blue_target_count)
    features["red_target_banned"] = float(red_target_count)

    return features


BAN_FEATURE_NAMES = [
    "blue_bans_count",
    "red_bans_count",
    "blue_target_banned",
    "red_target_banned",
]
