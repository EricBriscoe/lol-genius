from __future__ import annotations

SNAPSHOT_SECONDS = [300, 600, 900, 1200, 1500, 1800, 2100, 2400, 2700, 3000]

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
    "blue_inhibitors",
    "red_inhibitors",
    "blue_elder",
    "red_elder",
    "blue_cs",
    "red_cs",
    "cs_diff",
    "inhibitor_diff",
    "elder_diff",
    "first_blood_blue",
    "first_tower_blue",
    "first_dragon_blue",
]

# Gold excluded: Riot's Live Client Data API does not expose per-team gold totals.
# Train/inference features must match exactly, so gold is omitted from the live model.
_GOLD_COLS = {"blue_gold", "red_gold", "gold_diff"}
_PREGAME_ONLY_COLS = {"pregame_blue_win_prob"}

LIVE_FEATURE_NAMES = [f for f in TIMELINE_FEATURE_NAMES if f not in _GOLD_COLS] + ["pregame_blue_win_prob"]


def build_timeline_feature_matrix(db, model_type: str = "pregame") -> tuple:
    import pandas as pd

    rows = db.get_timeline_training_data()
    if not rows:
        return pd.DataFrame(), pd.Series(dtype=int), pd.Series(dtype=str), pd.Series(dtype=int)

    df = pd.DataFrame(rows)
    y = df.pop("blue_win").astype(int)
    match_ids = df.pop("match_id")
    game_creations = df.pop("game_creation")

    df["gold_diff"] = df["blue_gold"] - df["red_gold"]
    df["kill_diff"] = df["blue_kills"] - df["red_kills"]
    df["tower_diff"] = df["blue_towers"] - df["red_towers"]
    df["dragon_diff"] = df["blue_dragons"] - df["red_dragons"]
    df["cs_diff"] = df["blue_cs"] - df["red_cs"]
    df["inhibitor_diff"] = df["blue_inhibitors"] - df["red_inhibitors"]
    df["elder_diff"] = df["blue_elder"] - df["red_elder"]

    if model_type == "live":
        # Defaults to 0.5 (neutral) when pregame model hasn't run for this match.
        # The live model was trained with this column, so it must always be provided.
        df["pregame_blue_win_prob"] = df["pregame_blue_win_prob"].fillna(0.5).astype(float)
        feature_names = LIVE_FEATURE_NAMES
    else:
        feature_names = TIMELINE_FEATURE_NAMES

    X = df[feature_names].copy()
    return X, y, match_ids, game_creations
