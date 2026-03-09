from __future__ import annotations

import math

import numpy as np

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

_PREGAME_SUMMARY_COLS = [
    "avg_rank_diff",
    "rank_spread_diff",
    "avg_winrate_diff",
    "avg_mastery_diff",
    "melee_count_diff",
    "ad_ratio_diff",
    "total_games_diff",
    "hot_streak_count_diff",
    "veteran_count_diff",
    "mastery_level7_count_diff",
    "avg_champ_wr_diff",
    "scaling_score_diff",
    "max_scaling_score_diff",
    "stat_growth_diff",
]

_SCALING_INTERACTION_COLS = [
    "scaling_advantage_realized",
    "early_game_window_closing",
]

_MOMENTUM_COLS = [
    "kill_diff_delta",
    "cs_diff_delta",
    "tower_diff_delta",
]

_TEMPORAL_COLS = [
    "kill_lead_erosion",
    "tower_lead_erosion",
    "kill_rate_diff",
    "cs_rate_diff",
    "dragon_rate_diff",
    "kill_diff_accel",
    "recent_kill_share_diff",
    "game_phase_early",
    "game_phase_mid",
    "game_phase_late",
    "objective_density",
]

LIVE_FEATURE_NAMES = (
    [f for f in TIMELINE_FEATURE_NAMES if f not in _GOLD_COLS]
    + ["pregame_blue_win_prob"]
    + _PREGAME_SUMMARY_COLS
    + _SCALING_INTERACTION_COLS
    + _MOMENTUM_COLS
    + _TEMPORAL_COLS
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
) -> dict:
    b_ss = blue_scaling_scores or []
    r_ss = red_scaling_scores or []
    return {
        "avg_rank_diff": float(
            np.mean(blue_ranks or [_NEUTRAL_RANK])
            - np.mean(red_ranks or [_NEUTRAL_RANK])
        ),
        "rank_spread_diff": float(
            (np.std(blue_ranks) if len(blue_ranks) > 1 else 0.0)
            - (np.std(red_ranks) if len(red_ranks) > 1 else 0.0)
        ),
        "avg_winrate_diff": float(
            np.mean(blue_wrs or [0.5]) - np.mean(red_wrs or [0.5])
        ),
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
        "max_scaling_score_diff": float(
            (max(b_ss) if b_ss else 0.0) - (max(r_ss) if r_ss else 0.0)
        ),
        "stat_growth_diff": float(
            np.mean(blue_stat_growth or [0.0]) - np.mean(red_stat_growth or [0.0])
        ),
    }


def _extract_team_vectors(
    group, ddragon, champ_wrs=None, scaling_scores=None, stat_growth_fn=None
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
        return [
            math.log((row.get("mastery_points") or 0) + 1) for _, row in team.iterrows()
        ]

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
        return [
            (row.get("wins") or 0) + (row.get("losses") or 0)
            for _, row in team.iterrows()
        ]

    def _hot_streak_count(team):
        return sum(1 for _, row in team.iterrows() if (row.get("hot_streak") or 0) >= 1)

    def _veteran_count(team):
        return sum(1 for _, row in team.iterrows() if (row.get("veteran") or 0) >= 1)

    def _mastery7_count(team):
        return sum(
            1 for _, row in team.iterrows() if (row.get("mastery_level") or 0) >= 7
        )

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

    stat_growth_fn = ddragon.stat_growth_score if ddragon else None

    results = []
    for match_id, group in df.groupby("match_id"):
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
        ) = _extract_team_vectors(
            group, ddragon, champ_wrs, scaling_scores, stat_growth_fn
        )
        results.append(
            {
                "match_id": match_id,
                **compute_pregame_diff_stats(
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
                ),
            }
        )

    return pd.DataFrame(results)


def build_timeline_feature_matrix(
    db, model_type: str = "pregame", ddragon=None
) -> tuple:
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
        df["pregame_blue_win_prob"] = (
            df["pregame_blue_win_prob"].fillna(0.5).astype(float)
        )

        scaling_scores = db.get_champion_scaling_scores()
        if ddragon is not None:
            participant_rows = db.get_match_pregame_participants(
                match_ids.unique().tolist()
            )
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

        ssd = df["scaling_score_diff"]
        gts = df["game_time_seconds"]
        df["scaling_advantage_realized"] = ssd * (gts / 1800.0)
        df["early_game_window_closing"] = ssd * (1.0 - gts / 1500.0).clip(lower=0.0)

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

        df["kill_diff_accel"] = (
            df.groupby("__mid")["kill_diff_delta"].diff().fillna(0.0)
        )

        blue_kills_delta = df.groupby("__mid")["blue_kills"].diff().fillna(0.0)
        red_kills_delta = df.groupby("__mid")["red_kills"].diff().fillna(0.0)
        df["recent_kill_share_diff"] = blue_kills_delta / df["blue_kills"].clip(
            lower=1
        ) - red_kills_delta / df["red_kills"].clip(lower=1)

        gts_phase = df["game_time_seconds"]
        df["game_phase_early"] = (gts_phase <= 900).astype(float)
        df["game_phase_mid"] = ((gts_phase > 900) & (gts_phase <= 1500)).astype(float)
        df["game_phase_late"] = (gts_phase > 1500).astype(float)
        total_objectives = (
            df["blue_dragons"] + df["red_dragons"]
            + df["blue_barons"] + df["red_barons"]
            + df["blue_heralds"] + df["red_heralds"]
        )
        df["objective_density"] = total_objectives / game_minutes

        df = df.drop(columns=["__mid"])

        feature_names = LIVE_FEATURE_NAMES
    else:
        feature_names = TIMELINE_FEATURE_NAMES

    X = df[feature_names].copy()
    return X, y, match_ids, game_creations
