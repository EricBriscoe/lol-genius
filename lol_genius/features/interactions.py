from __future__ import annotations

import math
from collections import Counter

from lol_genius.api.ddragon import DataDragon
from lol_genius.features.draft import POSITION_ORDER, POSITION_SHORT

TAG_ADVANTAGE = {
    ("Assassin", "Mage"): 0.6,
    ("Tank", "Assassin"): 0.4,
    ("Fighter", "Tank"): 0.3,
    ("Marksman", "Assassin"): -0.5,
    ("Mage", "Fighter"): 0.3,
    ("Support", "Assassin"): -0.3,
}

ALL_TAGS = ["Tank", "Fighter", "Assassin", "Mage", "Marksman", "Support"]


def _get_champ_tags(champion_id: int, ddragon: DataDragon) -> list[str]:
    champ = ddragon.get_champion(champion_id)
    return champ.get("tags", []) if champ else []


def _tag_advantage_score(blue_tags: list[str], red_tags: list[str]) -> float:
    score = 0.0
    for bt in blue_tags:
        for rt in red_tags:
            score += TAG_ADVANTAGE.get((bt, rt), -TAG_ADVANTAGE.get((rt, bt), 0.0))
    return score


def _shannon_entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    entropy = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            entropy -= p * math.log2(p)
    return entropy


def extract_interaction_features(
    blue_by_pos: dict[str, dict],
    red_by_pos: dict[str, dict],
    blue_champ_feats: list[dict],
    red_champ_feats: list[dict],
    ddragon: DataDragon,
) -> dict[str, float]:
    features: dict[str, float] = {}

    blue_ap = 0
    blue_ad = 0
    red_ap = 0
    red_ad = 0
    blue_armor_sum = 0.0
    red_armor_sum = 0.0

    blue_tags_count: Counter[str] = Counter()
    red_tags_count: Counter[str] = Counter()
    blue_ranged_mage_mm = 0
    red_ranged_mage_mm = 0
    blue_engage = 0
    red_engage = 0

    for i, pos in enumerate(POSITION_ORDER):
        short = POSITION_SHORT[pos]
        bp = blue_by_pos.get(pos, {})
        rp = red_by_pos.get(pos, {})
        b_id = bp.get("champion_id", 0)
        r_id = rp.get("champion_id", 0)

        b_tags = _get_champ_tags(b_id, ddragon) if b_id else []
        r_tags = _get_champ_tags(r_id, ddragon) if r_id else []
        b_tag_set = set(b_tags)
        r_tag_set = set(r_tags)

        features[f"{short}_tag_advantage"] = _tag_advantage_score(b_tags, r_tags)

        b_range = ddragon.get_attack_range(b_id) if b_id else 550.0
        r_range = ddragon.get_attack_range(r_id) if r_id else 550.0
        features[f"{short}_range_diff"] = b_range - r_range

        b_melee = ddragon.is_melee(b_id) if b_id else False
        r_melee = ddragon.is_melee(r_id) if r_id else False
        if b_melee and not r_melee:
            features[f"{short}_melee_vs_ranged"] = 1.0
        elif not b_melee and r_melee:
            features[f"{short}_melee_vs_ranged"] = -1.0
        else:
            features[f"{short}_melee_vs_ranged"] = 0.0

        b_cf = blue_champ_feats[i] if i < len(blue_champ_feats) else {}
        r_cf = red_champ_feats[i] if i < len(red_champ_feats) else {}

        blue_ap += int(b_cf.get("is_ap_champ", 0))
        blue_ad += int(not b_cf.get("is_ap_champ", 0) and not b_cf.get("is_mixed_champ", 0))
        red_ap += int(r_cf.get("is_ap_champ", 0))
        red_ad += int(not r_cf.get("is_ap_champ", 0) and not r_cf.get("is_mixed_champ", 0))

        blue_armor_sum += b_cf.get("champ_armor_base", 33.0)
        red_armor_sum += r_cf.get("champ_armor_base", 33.0)

        for tag in ALL_TAGS:
            if tag in b_tag_set:
                blue_tags_count[tag] += 1
            if tag in r_tag_set:
                red_tags_count[tag] += 1

        if ("Mage" in b_tag_set or "Marksman" in b_tag_set) and not b_melee:
            blue_ranged_mage_mm += 1
        if ("Mage" in r_tag_set or "Marksman" in r_tag_set) and not r_melee:
            red_ranged_mage_mm += 1

        if b_melee and (b_tag_set & {"Tank", "Fighter"}):
            blue_engage += 1
        if r_melee and (r_tag_set & {"Tank", "Fighter"}):
            red_engage += 1

    features["team_ap_diff"] = float(blue_ap - red_ap)
    features["team_ad_diff"] = float(blue_ad - red_ad)

    blue_entropy = _shannon_entropy([blue_ap, blue_ad, max(0, 5 - blue_ap - blue_ad)])
    red_entropy = _shannon_entropy([red_ap, red_ad, max(0, 5 - red_ap - red_ad)])
    features["team_damage_diversity_diff"] = blue_entropy - red_entropy

    features["team_armor_vs_ap"] = (blue_armor_sum / 5.0) * red_ap - (red_armor_sum / 5.0) * blue_ap

    features["frontline_diff"] = float(
        (blue_tags_count["Tank"] + blue_tags_count["Fighter"])
        - (red_tags_count["Tank"] + red_tags_count["Fighter"])
    )
    features["engage_diff"] = float(blue_engage - red_engage)
    features["backline_diff"] = float(
        (blue_tags_count["Mage"] + blue_tags_count["Marksman"])
        - (red_tags_count["Mage"] + red_tags_count["Marksman"])
    )
    features["poke_diff"] = float(blue_ranged_mage_mm - red_ranged_mage_mm)
    features["peel_diff"] = float(
        (blue_tags_count["Support"] + blue_tags_count["Tank"])
        - (red_tags_count["Support"] + red_tags_count["Tank"])
    )
    features["dive_diff"] = float(
        (blue_tags_count["Assassin"] + blue_tags_count["Fighter"])
        - (red_tags_count["Assassin"] + red_tags_count["Fighter"])
    )

    return features


INTERACTION_FEATURE_NAMES: list[str] = []
for _pos in POSITION_ORDER:
    _short = POSITION_SHORT[_pos]
    INTERACTION_FEATURE_NAMES.extend(
        [
            f"{_short}_tag_advantage",
            f"{_short}_range_diff",
            f"{_short}_melee_vs_ranged",
        ]
    )
INTERACTION_FEATURE_NAMES.extend(
    [
        "team_ap_diff",
        "team_ad_diff",
        "team_damage_diversity_diff",
        "team_armor_vs_ap",
        "frontline_diff",
        "engage_diff",
        "backline_diff",
        "poke_diff",
        "peel_diff",
        "dive_diff",
    ]
)
