from __future__ import annotations

from lol_genius.api.ddragon import DataDragon

ALL_TAGS = ["Fighter", "Mage", "Assassin", "Tank", "Marksman", "Support"]


def extract_champion_features(champion_id: int, ddragon: DataDragon) -> dict:
    champ = ddragon.get_champion(champion_id)
    features: dict[str, float] = {}

    if not champ:
        features["champ_hp_base"] = 580.0
        features["champ_ad_base"] = 60.0
        features["champ_armor_base"] = 33.0
        features["champ_mr_base"] = 32.0
        features["champ_attack_range"] = 550.0
        features["champ_hp_per_level"] = 90.0
        features["champ_ad_per_level"] = 3.0
        features["is_ap_champ"] = 0.0
        features["is_mixed_champ"] = 0.0
        features["is_melee"] = 0.0
        features["champ_attack_score"] = 5.0
        features["champ_defense_score"] = 5.0
        features["champ_magic_score"] = 5.0
        features["champ_difficulty"] = 5.0
        for tag in ALL_TAGS:
            features[f"tag_{tag.lower()}"] = 0.0
        return features

    stats = champ.get("stats", {})
    features["champ_hp_base"] = float(stats.get("hp", 580))
    features["champ_ad_base"] = float(stats.get("attackdamage", 60))
    features["champ_armor_base"] = float(stats.get("armor", 33))
    features["champ_mr_base"] = float(stats.get("spellblock", 32))
    features["champ_attack_range"] = float(stats.get("attackrange", 550))
    features["champ_hp_per_level"] = float(stats.get("hpperlevel", 90))
    features["champ_ad_per_level"] = float(stats.get("attackdamageperlevel", 3))

    dmg_type = ddragon.classify_damage_type(champion_id)
    features["is_ap_champ"] = 1.0 if dmg_type == "AP" else 0.0
    features["is_mixed_champ"] = 1.0 if dmg_type == "MIXED" else 0.0
    features["is_melee"] = 1.0 if ddragon.is_melee(champion_id) else 0.0

    info = champ.get("info", {})
    features["champ_attack_score"] = float(info.get("attack", 5))
    features["champ_defense_score"] = float(info.get("defense", 5))
    features["champ_magic_score"] = float(info.get("magic", 5))
    features["champ_difficulty"] = float(info.get("difficulty", 5))

    tags = set(champ.get("tags", []))
    for tag in ALL_TAGS:
        features[f"tag_{tag.lower()}"] = 1.0 if tag in tags else 0.0

    return features


CHAMPION_FEATURE_NAMES = [
    "champ_hp_base",
    "champ_ad_base",
    "champ_armor_base",
    "champ_mr_base",
    "champ_attack_range",
    "champ_hp_per_level",
    "champ_ad_per_level",
    "is_ap_champ",
    "is_mixed_champ",
    "is_melee",
    "champ_attack_score",
    "champ_defense_score",
    "champ_magic_score",
    "champ_difficulty",
    "tag_fighter",
    "tag_mage",
    "tag_assassin",
    "tag_tank",
    "tag_marksman",
    "tag_support",
]
