from __future__ import annotations

import logging

import pandas as pd
from tqdm import tqdm

from lol_genius.api.ddragon import DataDragon
from lol_genius.db.queries import MatchDB
from lol_genius.features.bans import BAN_FEATURE_NAMES, extract_ban_features
from lol_genius.features.champion import CHAMPION_FEATURE_NAMES, extract_champion_features
from lol_genius.features.draft import DRAFT_FEATURE_NAMES, POSITION_ORDER, POSITION_SHORT, align_by_position, extract_draft_features
from lol_genius.features.player import PLAYER_FEATURE_NAMES, extract_player_features, compute_tilt_features
from lol_genius.features.team import TEAM_FEATURE_NAMES, extract_team_features

log = logging.getLogger(__name__)


def _patch_to_numeric(patch: str) -> float:
    parts = patch.split(".")
    if len(parts) >= 2:
        return int(parts[0]) * 100 + int(parts[1])
    return 0.0


def build_feature_matrix(
    db: MatchDB, ddragon: DataDragon, patch: str | None = None
) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    match_ids = db.get_all_matches_for_training(patch)
    log.info(f"Building features for {len(match_ids)} matches")

    global_champ_wr = db.get_champion_patch_winrates(patch)

    rows = []
    targets = []
    patches = []
    timestamps = []

    for match_id in tqdm(match_ids, desc="Building features", unit="match"):
        match = db.get_match(match_id)
        if not match:
            continue

        participants = db.get_participants_for_match(match_id)
        if len(participants) != 10:
            continue

        blue = [p for p in participants if p["team_id"] == 100]
        red = [p for p in participants if p["team_id"] == 200]

        if len(blue) != 5 or len(red) != 5:
            continue

        game_creation = match.get("game_creation", 0)
        row = _build_match_features(db, ddragon, blue, red, patch_str=match.get("patch", ""), match_id=match_id, game_creation=game_creation, global_champ_wr=global_champ_wr)
        if row is not None:
            rows.append(row)
            targets.append(match["blue_win"])
            patches.append(match.get("patch", ""))
            timestamps.append(game_creation)

    if not rows:
        return pd.DataFrame(), pd.Series(dtype=float), pd.Series(dtype=str), pd.Series(dtype=int)

    X = pd.DataFrame(rows)
    y = pd.Series(targets, name="blue_win")
    patch_series = pd.Series(patches, name="patch")
    timestamp_series = pd.Series(timestamps, name="game_creation")
    log.info(f"Feature matrix: {X.shape[0]} matches, {X.shape[1]} features")
    return X, y, patch_series, timestamp_series


def _build_match_features(
    db: MatchDB, ddragon: DataDragon, blue: list[dict], red: list[dict],
    patch_str: str = "", match_id: str | None = None,
    game_creation: int | None = None,
    global_champ_wr: dict[int, dict] | None = None,
) -> dict | None:
    features: dict[str, float] = {"patch_numeric": _patch_to_numeric(patch_str)}

    blue_by_pos = align_by_position(blue)
    red_by_pos = align_by_position(red)

    blue_player_feats = {}
    red_player_feats = {}
    blue_champ_feats_list = []
    red_champ_feats_list = []
    blue_player_feats_list = []
    red_player_feats_list = []

    blue_top_champs: dict[str, list[int]] = {}
    red_top_champs: dict[str, list[int]] = {}

    for side, team, pf_by_pos, pf_list, cf_list, top_champs in [
        ("blue", blue_by_pos, blue_player_feats, blue_player_feats_list, blue_champ_feats_list, blue_top_champs),
        ("red", red_by_pos, red_player_feats, red_player_feats_list, red_champ_feats_list, red_top_champs),
    ]:
        for pos in POSITION_ORDER:
            p = team.get(pos)
            if not p:
                pf = {k: 0.0 for k in PLAYER_FEATURE_NAMES}
                cf = {k: 0.0 for k in CHAMPION_FEATURE_NAMES}
            else:
                puuid = p["puuid"]
                champion_id = p["champion_id"]

                rank = db.get_latest_rank(puuid)
                mastery = db.get_champion_mastery_record(puuid, champion_id)
                recent = db.compute_recent_stats_from_db(puuid, exclude_match_id=match_id, before_time_ms=game_creation)
                champ_stats = db.get_player_champion_stats(puuid, champion_id, patch=patch_str or None, exclude_match_id=match_id, before_time_ms=game_creation)
                role_dist = db.get_player_role_distribution(puuid, exclude_match_id=match_id, before_time_ms=game_creation)

                pf = extract_player_features(p, rank, mastery, recent, champ_stats, role_dist)
                cf = extract_champion_features(champion_id, ddragon)

                champ_global = (global_champ_wr or {}).get(champion_id, {})
                pf["champ_global_wr"] = champ_global.get("winrate", 0.5)

                recent_outcomes = db.get_player_recent_outcomes(puuid, exclude_match_id=match_id, before_time_ms=game_creation)
                tilt_feats = compute_tilt_features(recent_outcomes)
                pf.update(tilt_feats)

                top_champs[puuid] = db.get_player_top_champions(puuid, limit=3)

            pf_by_pos[pos] = pf
            pf_list.append(pf)
            cf_list.append(cf)

            short = POSITION_SHORT[pos]
            for k, v in pf.items():
                features[f"{side}_{short}_{k}"] = v
            for k, v in cf.items():
                features[f"{side}_{short}_{k}"] = v

    blue_team = extract_team_features(blue_player_feats_list, blue_champ_feats_list)
    red_team = extract_team_features(red_player_feats_list, red_champ_feats_list)

    for k, v in blue_team.items():
        features[f"blue_{k}"] = v
    for k, v in red_team.items():
        features[f"red_{k}"] = v

    draft = extract_draft_features(
        blue_by_pos, red_by_pos, blue_player_feats, red_player_feats
    )
    features.update(draft)

    bans = db.get_match_bans(match_id) if match_id else []
    ban_feats = extract_ban_features(bans, blue_top_champs, red_top_champs)
    features.update(ban_feats)

    return features


def get_feature_names() -> list[str]:
    names = ["patch_numeric"]
    for side in ["blue", "red"]:
        for pos in POSITION_ORDER:
            short = POSITION_SHORT[pos]
            for feat in PLAYER_FEATURE_NAMES:
                names.append(f"{side}_{short}_{feat}")
            for feat in CHAMPION_FEATURE_NAMES:
                names.append(f"{side}_{short}_{feat}")
    for side in ["blue", "red"]:
        for feat in TEAM_FEATURE_NAMES:
            names.append(f"{side}_{feat}")
    names.extend(DRAFT_FEATURE_NAMES)
    names.extend(BAN_FEATURE_NAMES)
    return names
