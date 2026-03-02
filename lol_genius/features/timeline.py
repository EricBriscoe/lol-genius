from __future__ import annotations

TIMELINE_FEATURE_NAMES = [
    "game_time_seconds",
    "blue_gold",
    "red_gold",
    "gold_diff",
    "blue_kills",
    "red_kills",
    "kill_diff",
    "blue_towers",
    "red_towers",
    "tower_diff",
    "blue_dragons",
    "red_dragons",
    "dragon_diff",
    "blue_barons",
    "red_barons",
    "blue_heralds",
    "red_heralds",
    "first_blood_blue",
    "first_tower_blue",
    "first_dragon_blue",
]


def build_timeline_feature_matrix(db) -> tuple:
    import pandas as pd

    rows = db.get_timeline_training_data()
    if not rows:
        return pd.DataFrame(), pd.Series(dtype=int)

    df = pd.DataFrame(rows)
    y = df.pop("blue_win").astype(int)

    df["gold_diff"] = df["blue_gold"] - df["red_gold"]
    df["kill_diff"] = df["blue_kills"] - df["red_kills"]
    df["tower_diff"] = df["blue_towers"] - df["red_towers"]
    df["dragon_diff"] = df["blue_dragons"] - df["red_dragons"]

    X = df[TIMELINE_FEATURE_NAMES].copy()
    return X, y
