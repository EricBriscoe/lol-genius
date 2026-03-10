from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

_SHARED_DIR = Path(__file__).resolve().parents[2] / "shared"

with open(_SHARED_DIR / "live-feature-names.json") as _f:
    _FEAT_JSON = json.load(_f)

SNAPSHOT_SECONDS = _FEAT_JSON["snapshot_seconds"]

TIMELINE_FEATURE_NAMES = _FEAT_JSON["timeline_feature_names"]

_GOLD_COLS = set(_FEAT_JSON["gold_cols"])

_PREGAME_SUMMARY_COLS = _FEAT_JSON["pregame_summary_cols"]

_MOMENTUM_COLS = _FEAT_JSON["momentum_cols"]

_TEMPORAL_COLS = _FEAT_JSON["temporal_cols"]

_LEVEL_COLS = _FEAT_JSON["level_cols"]

_DRAGON_SOUL_COLS = _FEAT_JSON["dragon_soul_cols"]

_POSITIONS = _FEAT_JSON["positions"]

_PER_ROLE_STATS = _FEAT_JSON["per_role_stats"]

_PER_ROLE_COLS = [f"{pos}_{stat}_diff" for pos in _POSITIONS for stat in _PER_ROLE_STATS]

LIVE_FEATURE_NAMES = (
    [f for f in TIMELINE_FEATURE_NAMES if f not in _GOLD_COLS]
    + _PREGAME_SUMMARY_COLS
    + _MOMENTUM_COLS
    + _TEMPORAL_COLS
    + _LEVEL_COLS
    + _DRAGON_SOUL_COLS
    + _PER_ROLE_COLS
)

assert not any(col in LIVE_FEATURE_NAMES for col in _GOLD_COLS), (
    "Gold columns must not appear in live features"
)

# GOLD II 0 LP on the rank_to_numeric scale (TIER_MAP["GOLD"]=12 + DIV_MAP["II"]=2 + 0 LP)
_NEUTRAL_RANK = 14.0
_TEAM_SIZE = 5


def compute_pregame_diff_stats(
    blue_ranks: list[float],
    red_ranks: list[float],
    blue_wrs: list[float],
    red_wrs: list[float],
    blue_masteries: list[float],
    red_masteries: list[float],
    blue_melee: int,
    red_melee: int,
    blue_ad: int,
    red_ad: int,
    *,
    blue_total_games=None,
    red_total_games=None,
    blue_hot_streaks: int = 0,
    red_hot_streaks: int = 0,
    blue_veterans: int = 0,
    red_veterans: int = 0,
    blue_mastery7: int = 0,
    red_mastery7: int = 0,
    blue_champ_wrs=None,
    red_champ_wrs=None,
    blue_scaling_scores: list[float] | None = None,
    red_scaling_scores: list[float] | None = None,
    blue_stat_growth: list[float] | None = None,
    red_stat_growth: list[float] | None = None,
    blue_scaling_tiers: list[int] | None = None,
    red_scaling_tiers: list[int] | None = None,
    blue_infinite_scalers: int = 0,
    red_infinite_scalers: int = 0,
) -> dict:
    b_ss = blue_scaling_scores or []
    r_ss = red_scaling_scores or []
    return {
        "avg_rank_diff": float(
            np.mean(blue_ranks or [_NEUTRAL_RANK]) - np.mean(red_ranks or [_NEUTRAL_RANK])
        ),
        "rank_spread_diff": float(
            (np.std(blue_ranks) if len(blue_ranks) > 1 else 0.0)
            - (np.std(red_ranks) if len(red_ranks) > 1 else 0.0)
        ),
        "avg_winrate_diff": float(np.mean(blue_wrs or [0.5]) - np.mean(red_wrs or [0.5])),
        "avg_mastery_diff": float(
            (np.mean(blue_masteries) if blue_masteries else 0.0)
            - (np.mean(red_masteries) if red_masteries else 0.0)
        ),
        "melee_count_diff": float(blue_melee - red_melee),
        "ad_ratio_diff": float(blue_ad / _TEAM_SIZE - red_ad / _TEAM_SIZE),
        "total_games_diff": float(
            np.mean(blue_total_games or [0]) - np.mean(red_total_games or [0])
        ),
        "hot_streak_count_diff": float(blue_hot_streaks - red_hot_streaks),
        "veteran_count_diff": float(blue_veterans - red_veterans),
        "mastery_level7_count_diff": float(blue_mastery7 - red_mastery7),
        "avg_champ_wr_diff": float(
            np.mean(blue_champ_wrs or [0.5]) - np.mean(red_champ_wrs or [0.5])
        ),
        "scaling_score_diff": float(np.mean(b_ss or [0.0]) - np.mean(r_ss or [0.0])),
        "stat_growth_diff": float(
            np.mean(blue_stat_growth or [0.0]) - np.mean(red_stat_growth or [0.0])
        ),
        "infinite_scaler_count_diff": float(blue_infinite_scalers - red_infinite_scalers),
    }


def _extract_team_vectors(
    group,
    ddragon,
    champ_wrs=None,
    scaling_scores=None,
    stat_growth_fn=None,
    infinite_scaler_fn=None,
):
    from lol_genius.features.player import rank_to_numeric

    blue = group[group["team_id"] == 100]
    red = group[group["team_id"] == 200]

    def _ranks(team):
        return [
            rank_to_numeric(row["tier"], row["rank"], row.get("league_points") or 0)
            for _, row in team.iterrows()
            if row.get("tier") and row.get("rank")
        ]

    def _winrates(team):
        out = []
        for _, row in team.iterrows():
            w, losses = row.get("wins") or 0, row.get("losses") or 0
            if (w + losses) > 0:
                out.append(w / (w + losses))
        return out

    def _masteries(team):
        return [math.log((row.get("mastery_points") or 0) + 1) for _, row in team.iterrows()]

    def _melee_count(team):
        return sum(
            1
            for _, row in team.iterrows()
            if row.get("champion_id") and ddragon.is_melee(int(row["champion_id"]))
        )

    def _ad_count(team):
        return sum(
            1
            for _, row in team.iterrows()
            if row.get("champion_id")
            and ddragon.classify_damage_type(int(row["champion_id"])) == "AD"
        )

    def _total_games(team):
        return [(row.get("wins") or 0) + (row.get("losses") or 0) for _, row in team.iterrows()]

    def _hot_streak_count(team):
        return sum(1 for _, row in team.iterrows() if (row.get("hot_streak") or 0) >= 1)

    def _veteran_count(team):
        return sum(1 for _, row in team.iterrows() if (row.get("veteran") or 0) >= 1)

    def _mastery7_count(team):
        return sum(1 for _, row in team.iterrows() if (row.get("mastery_level") or 0) >= 7)

    def _champ_wrs_list(team):
        out = []
        for _, row in team.iterrows():
            cid = row.get("champion_id")
            if cid and int(cid) in (champ_wrs or {}):
                out.append((champ_wrs or {})[int(cid)]["winrate"])
        return out

    def _scaling_scores_list(team):
        out = []
        for _, row in team.iterrows():
            cid = row.get("champion_id")
            if cid and scaling_scores and int(cid) in scaling_scores:
                out.append(scaling_scores[int(cid)])
        return out

    def _stat_growth_list(team):
        out = []
        for _, row in team.iterrows():
            cid = row.get("champion_id")
            if cid and stat_growth_fn:
                out.append(stat_growth_fn(int(cid)))
        return out

    def _infinite_scaler_count(team):
        if not infinite_scaler_fn:
            return 0
        return sum(
            1
            for _, row in team.iterrows()
            if row.get("champion_id") and infinite_scaler_fn(int(row["champion_id"]))
        )

    return (
        _ranks(blue),
        _ranks(red),
        _winrates(blue),
        _winrates(red),
        _masteries(blue),
        _masteries(red),
        _melee_count(blue),
        _melee_count(red),
        _ad_count(blue),
        _ad_count(red),
        _total_games(blue),
        _total_games(red),
        _hot_streak_count(blue),
        _hot_streak_count(red),
        _veteran_count(blue),
        _veteran_count(red),
        _mastery7_count(blue),
        _mastery7_count(red),
        _champ_wrs_list(blue),
        _champ_wrs_list(red),
        _scaling_scores_list(blue),
        _scaling_scores_list(red),
        _stat_growth_list(blue),
        _stat_growth_list(red),
        _infinite_scaler_count(blue),
        _infinite_scaler_count(red),
    )


def compute_pregame_diff_from_group(
    group,
    ddragon,
    champ_wrs=None,
    scaling_scores=None,
) -> dict:
    stat_growth_fn = ddragon.stat_growth_score if ddragon else None
    infinite_scaler_fn = ddragon.is_infinite_scaler if ddragon else None
    (
        b_ranks,
        r_ranks,
        b_wrs,
        r_wrs,
        b_mast,
        r_mast,
        b_melee,
        r_melee,
        b_ad,
        r_ad,
        b_tg,
        r_tg,
        b_hs,
        r_hs,
        b_vet,
        r_vet,
        b_m7,
        r_m7,
        b_cwr,
        r_cwr,
        b_ss,
        r_ss,
        b_sg,
        r_sg,
        b_inf,
        r_inf,
    ) = _extract_team_vectors(
        group,
        ddragon,
        champ_wrs,
        scaling_scores,
        stat_growth_fn,
        infinite_scaler_fn,
    )
    return compute_pregame_diff_stats(
        b_ranks,
        r_ranks,
        b_wrs,
        r_wrs,
        b_mast,
        r_mast,
        b_melee,
        r_melee,
        b_ad,
        r_ad,
        blue_total_games=b_tg,
        red_total_games=r_tg,
        blue_hot_streaks=b_hs,
        red_hot_streaks=r_hs,
        blue_veterans=b_vet,
        red_veterans=r_vet,
        blue_mastery7=b_m7,
        red_mastery7=r_m7,
        blue_champ_wrs=b_cwr,
        red_champ_wrs=r_cwr,
        blue_scaling_scores=b_ss,
        red_scaling_scores=r_ss,
        blue_stat_growth=b_sg,
        red_stat_growth=r_sg,
        blue_infinite_scalers=b_inf,
        red_infinite_scalers=r_inf,
    )


def _compute_pregame_summaries(
    participant_rows: list[dict],
    ddragon,
    champ_wrs=None,
    scaling_scores=None,
):
    import pandas as pd

    df = pd.DataFrame(participant_rows)
    if df.empty:
        return pd.DataFrame()

    results = []
    for match_id, group in df.groupby("match_id"):
        results.append(
            {
                "match_id": match_id,
                **compute_pregame_diff_from_group(
                    group,
                    ddragon,
                    champ_wrs,
                    scaling_scores,
                ),
            }
        )

    return pd.DataFrame(results)


def build_timeline_feature_matrix(db, model_type: str = "pregame", ddragon=None) -> tuple:
    import pandas as pd

    rows = db.get_timeline_training_data()
    if not rows:
        return (
            pd.DataFrame(),
            pd.Series(dtype=int),
            pd.Series(dtype=str),
            pd.Series(dtype=int),
        )

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
        scaling_scores = db.get_champion_scaling_scores()
        if ddragon is not None:
            participant_rows = db.get_match_pregame_participants(match_ids.unique().tolist())
            if participant_rows:
                champ_wrs = db.get_champion_patch_winrates()
                pregame_df = _compute_pregame_summaries(
                    participant_rows, ddragon, champ_wrs, scaling_scores
                )
                if not pregame_df.empty:
                    df["__mid"] = match_ids.values
                    df = df.merge(
                        pregame_df, left_on="__mid", right_on="match_id", how="left"
                    ).drop(columns=["__mid", "match_id"])

        for col in _PREGAME_SUMMARY_COLS:
            if col not in df.columns:
                df[col] = 0.0
        df[_PREGAME_SUMMARY_COLS] = df[_PREGAME_SUMMARY_COLS].fillna(0.0)

        df["avg_level_diff"] = df["blue_avg_level"] - df["red_avg_level"]
        df["max_level_diff"] = df["blue_max_level"] - df["red_max_level"]

        df["blue_has_soul"] = (df["blue_dragons"] >= 4).astype(float)
        df["red_has_soul"] = (df["red_dragons"] >= 4).astype(float)
        df["blue_soul_point"] = (df["blue_dragons"] >= 3).astype(float)
        df["red_soul_point"] = (df["red_dragons"] >= 3).astype(float)

        df["__mid"] = match_ids.values
        df = df.sort_values(["__mid", "game_time_seconds"])
        for col in _MOMENTUM_COLS:
            src = col.replace("_delta", "")
            df[col] = df.groupby("__mid")[src].diff().fillna(0.0)

        df["__abs_kd"] = df["kill_diff"].abs()
        df["kill_lead_erosion"] = df.groupby("__mid")["__abs_kd"].cummax() - df["__abs_kd"]
        df["__abs_td"] = df["tower_diff"].abs()
        df["tower_lead_erosion"] = df.groupby("__mid")["__abs_td"].cummax() - df["__abs_td"]
        df.drop(columns=["__abs_kd", "__abs_td"], inplace=True)

        game_minutes = (df["game_time_seconds"] / 60.0).clip(lower=1.0)
        df["kill_rate_diff"] = df["kill_diff"] / game_minutes
        df["cs_rate_diff"] = df["cs_diff"] / game_minutes
        df["dragon_rate_diff"] = df["dragon_diff"] / game_minutes

        df["kill_diff_accel"] = df.groupby("__mid")["kill_diff_delta"].diff().fillna(0.0)

        blue_kills_delta = df.groupby("__mid")["blue_kills"].diff().fillna(0.0)
        red_kills_delta = df.groupby("__mid")["red_kills"].diff().fillna(0.0)
        df["recent_kill_share_diff"] = blue_kills_delta / df["blue_kills"].clip(
            lower=1
        ) - red_kills_delta / df["red_kills"].clip(lower=1)

        total_objectives = (
            df["blue_dragons"]
            + df["red_dragons"]
            + df["blue_barons"]
            + df["red_barons"]
            + df["blue_heralds"]
            + df["red_heralds"]
        )
        df["objective_density"] = total_objectives / game_minutes

        for pos in _POSITIONS:
            blue_cs = f"blue_{pos}_cs"
            red_cs = f"red_{pos}_cs"
            blue_lvl = f"blue_{pos}_level"
            red_lvl = f"red_{pos}_level"
            blue_k = f"blue_{pos}_kills"
            red_k = f"red_{pos}_kills"
            if blue_cs in df.columns:
                df[f"{pos}_cs_diff"] = df[blue_cs].fillna(0) - df[red_cs].fillna(0)
            else:
                df[f"{pos}_cs_diff"] = 0.0
            if blue_lvl in df.columns:
                df[f"{pos}_level_diff"] = df[blue_lvl].fillna(1) - df[red_lvl].fillna(1)
            else:
                df[f"{pos}_level_diff"] = 0.0
            if blue_k in df.columns:
                df[f"{pos}_kill_diff"] = df[blue_k].fillna(0) - df[red_k].fillna(0)
            else:
                df[f"{pos}_kill_diff"] = 0.0

        df = df.drop(columns=["__mid"])

        feature_names = LIVE_FEATURE_NAMES
    else:
        feature_names = TIMELINE_FEATURE_NAMES

    X = df[feature_names].copy()
    return X, y, match_ids, game_creations
