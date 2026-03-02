from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from lol_genius.api.ddragon import DataDragon
from lol_genius.api.proxy_client import ProxyClient
from lol_genius.db.queries import MatchDB
from lol_genius.features.bans import extract_ban_features
from lol_genius.features.champion import (
    CHAMPION_FEATURE_NAMES,
    extract_champion_features,
)
from lol_genius.features.draft import (
    POSITION_ORDER,
    POSITION_SHORT,
    align_by_position,
    extract_draft_features,
)
from lol_genius.features.interactions import extract_interaction_features
from lol_genius.features.player import (
    PLAYER_FEATURE_NAMES,
    extract_player_features,
    compute_tilt_features,
)
from lol_genius.features.stats import aggregate_recent_stats, normalize_api_match_row
from lol_genius.features.team import extract_team_features
from lol_genius.model.explain import explain_single_match
from lol_genius.model.train import load_model

log = logging.getLogger(__name__)

SMITE_ID = 11
LIVE_MATCH_FETCH_COUNT = 5


def infer_positions(participants: list[dict], ddragon: DataDragon) -> list[dict]:
    for team_id in (100, 200):
        team = [p for p in participants if p["team_id"] == team_id]
        assigned: dict[str, dict] = {}
        unassigned: list[dict] = []

        for p in team:
            spells = {p.get("summoner1_id", 0), p.get("summoner2_id", 0)}
            if SMITE_ID in spells:
                p["team_position"] = "JUNGLE"
                assigned["JUNGLE"] = p
            else:
                unassigned.append(p)

        for p in unassigned:
            champ = ddragon.get_champion(p["champion_id"])
            p["_tags"] = set(champ.get("tags", [])) if champ else set()

        remaining = list(unassigned)
        for pos, tag_check in [
            ("UTILITY", lambda t: "Support" in t),
            ("BOTTOM", lambda t: "Marksman" in t),
            ("MIDDLE", lambda t: "Mage" in t or "Assassin" in t),
            ("TOP", lambda t: "Tank" in t or "Fighter" in t),
        ]:
            if pos in assigned:
                continue
            candidates = [p for p in remaining if tag_check(p.get("_tags", set()))]
            if len(candidates) == 1:
                candidates[0]["team_position"] = pos
                assigned[pos] = candidates[0]
                remaining.remove(candidates[0])

        remaining_positions = [pos for pos in POSITION_ORDER if pos not in assigned]
        for p, pos in zip(remaining, remaining_positions):
            p["team_position"] = pos

        for p in team:
            p.pop("_tags", None)

    return participants


def _compute_stats_from_matches(
    puuid: str,
    champion_id: int,
    matches: list[dict],
) -> dict:
    stat_rows: list[dict] = []
    champ_games = 0
    champ_wins = 0
    role_counts: dict[str, int] = {}
    recent_outcomes = []

    for match in matches:
        info = match.get("info", {})
        participants = info.get("participants", [])
        player = next((p for p in participants if p.get("puuid") == puuid), None)
        if not player:
            continue

        row = normalize_api_match_row(puuid, match)
        if row:
            stat_rows.append(row)

        if player.get("championId") == champion_id:
            champ_games += 1
            if player.get("win"):
                champ_wins += 1

        pos = player.get("teamPosition", "")
        if pos:
            role_counts[pos] = role_counts.get(pos, 0) + 1

        recent_outcomes.append(
            {
                "win": player.get("win", False),
                "game_creation": info.get("gameCreation", 0),
                "game_duration": info.get("gameDuration", 1),
            }
        )

    return {
        "recent_stats": aggregate_recent_stats(puuid, stat_rows),
        "champ_stats": {
            "games": champ_games,
            "wins": champ_wins,
            "winrate": champ_wins / champ_games if champ_games > 0 else 0.0,
        },
        "role_dist": role_counts,
        "recent_outcomes": recent_outcomes,
    }


def _enrich_participant(
    proxy: ProxyClient,
    db: MatchDB,
    puuid: str,
    champion_id: int,
) -> dict:
    rank = db.get_latest_rank(puuid)
    if not rank:
        entries = proxy.get_league_by_puuid(puuid)
        for entry in entries or []:
            if entry.get("queueType") == "RANKED_SOLO_5x5":
                rank = {
                    "tier": entry.get("tier", "GOLD"),
                    "rank": entry.get("rank", "IV"),
                    "league_points": entry.get("leaguePoints", 0),
                    "wins": entry.get("wins", 0),
                    "losses": entry.get("losses", 0),
                    "hot_streak": entry.get("hotStreak", False),
                    "fresh_blood": entry.get("freshBlood", False),
                    "veteran": entry.get("veteran", False),
                }
                break

    mastery = db.get_champion_mastery_record(puuid, champion_id)
    if not mastery:
        api_mastery = proxy.get_champion_mastery(puuid, champion_id)
        if api_mastery:
            mastery = {
                "mastery_points": api_mastery.get("championPoints", 0),
                "mastery_level": api_mastery.get("championLevel", 0),
                "last_play_time": api_mastery.get("lastPlayTime", 0),
            }

    recent_stats = db.compute_recent_stats_from_db(puuid)
    champ_stats = db.get_player_champion_stats(puuid, champion_id)
    role_dist = db.get_player_role_distribution(puuid)
    recent_outcomes = db.get_player_recent_outcomes(puuid)

    needs_api = (
        not recent_stats
        or champ_stats.get("games", 0) == 0
        or not role_dist
        or not recent_outcomes
    )
    if needs_api:
        log.info(
            f"Incomplete DB data for {puuid[:8]}…, fetching recent matches from API"
        )
        match_ids = proxy.get_match_ids(puuid, count=LIVE_MATCH_FETCH_COUNT, queue=420)
        if match_ids:
            with ThreadPoolExecutor(max_workers=len(match_ids)) as pool:
                fetched = list(pool.map(proxy.get_match, match_ids))
            matches = [m for m in fetched if m is not None]
            if matches:
                api_stats = _compute_stats_from_matches(puuid, champion_id, matches)
                if not recent_stats:
                    recent_stats = api_stats["recent_stats"]
                if champ_stats.get("games", 0) == 0:
                    champ_stats = api_stats["champ_stats"]
                if not role_dist:
                    role_dist = api_stats["role_dist"]
                if not recent_outcomes:
                    recent_outcomes = api_stats["recent_outcomes"]

    top_champs = db.get_player_top_champions(puuid, limit=3)
    if not top_champs:
        top_masteries = proxy.get_top_masteries(puuid, count=3)
        top_champs = [e.get("championId", 0) for e in top_masteries]

    return {
        "rank": rank,
        "mastery": mastery,
        "recent_stats": recent_stats,
        "champ_stats": champ_stats,
        "role_dist": role_dist,
        "recent_outcomes": recent_outcomes,
        "top_champs": top_champs,
    }


def _build_live_features(
    ddragon: DataDragon,
    db: MatchDB,
    blue: list[dict],
    red: list[dict],
    bans: list[dict],
) -> dict | None:
    features: dict[str, float] = {"patch_numeric": 0.0}

    blue_by_pos = align_by_position(blue)
    red_by_pos = align_by_position(red)

    blue_player_feats: dict[str, dict] = {}
    red_player_feats: dict[str, dict] = {}
    blue_champ_feats_list: list[dict] = []
    red_champ_feats_list: list[dict] = []
    blue_player_feats_list: list[dict] = []
    red_player_feats_list: list[dict] = []
    blue_top_champs: dict[str, list[int]] = {}
    red_top_champs: dict[str, list[int]] = {}

    global_champ_wr = db.get_champion_patch_winrates()

    for side, team, pf_by_pos, pf_list, cf_list, top_champs_map in [
        (
            "blue",
            blue_by_pos,
            blue_player_feats,
            blue_player_feats_list,
            blue_champ_feats_list,
            blue_top_champs,
        ),
        (
            "red",
            red_by_pos,
            red_player_feats,
            red_player_feats_list,
            red_champ_feats_list,
            red_top_champs,
        ),
    ]:
        for pos in POSITION_ORDER:
            p = team.get(pos)
            if not p:
                pf = {k: 0.0 for k in PLAYER_FEATURE_NAMES}
                cf = {k: 0.0 for k in CHAMPION_FEATURE_NAMES}
            else:
                enr = p.get("_enrichment", {})
                pf = extract_player_features(
                    p,
                    enr.get("rank"),
                    enr.get("mastery"),
                    enr.get("recent_stats"),
                    enr.get("champ_stats"),
                    enr.get("role_dist"),
                )

                champ_global = (global_champ_wr or {}).get(p["champion_id"], {})
                pf["champ_global_wr"] = champ_global.get("winrate", 0.5)

                tilt_feats = compute_tilt_features(enr.get("recent_outcomes", []))
                pf.update(tilt_feats)

                cf = extract_champion_features(p["champion_id"], ddragon)
                top_champs_map[p["puuid"]] = enr.get("top_champs", [])

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

    interaction = extract_interaction_features(
        blue_by_pos,
        red_by_pos,
        blue_champ_feats_list,
        red_champ_feats_list,
        ddragon,
    )
    features.update(interaction)

    ban_feats = extract_ban_features(bans, blue_top_champs, red_top_champs)
    features.update(ban_feats)

    return features


def predict_live_game(
    proxy: ProxyClient,
    db: MatchDB,
    ddragon: DataDragon,
    model_dir: str,
    spectator_data: dict,
    dsn: str | None = None,
) -> dict:
    model, feature_names = load_model(model_dir)

    raw = spectator_data.get("participants", [])
    if len(raw) != 10:
        raise ValueError(f"Expected 10 participants, got {len(raw)}")

    for p in raw:
        if not p.get("puuid"):
            p["puuid"] = f"bot_{p.get('championId', 0)}"
            p["_is_bot"] = True
        p["summoner1_id"] = p.get("spell1Id", 0)
        p["summoner2_id"] = p.get("spell2Id", 0)
        p["champion_id"] = p.get("championId", 0)
        p["team_id"] = p.get("teamId", 100)

    infer_positions(raw, ddragon)

    blue = [p for p in raw if p["team_id"] == 100]
    red = [p for p in raw if p["team_id"] == 200]

    def _enrich_player(p: dict) -> None:
        if p.get("_is_bot"):
            p["summoner_level"] = 0
            p["_enrichment"] = {
                "rank": None,
                "mastery": None,
                "recent_stats": None,
                "champ_stats": {"games": 0, "wins": 0, "winrate": 0.0},
                "role_dist": {},
                "recent_outcomes": [],
                "top_champs": [],
            }
            return
        summoner = proxy.get_summoner_by_puuid(p["puuid"])
        p["summoner_level"] = summoner.get("summonerLevel", 0) if summoner else 0
        if dsn:
            thread_db = MatchDB(dsn)
            try:
                p["_enrichment"] = _enrich_participant(
                    proxy, thread_db, p["puuid"], p["champion_id"]
                )
            finally:
                thread_db.close()
        else:
            p["_enrichment"] = _enrich_participant(
                proxy, db, p["puuid"], p["champion_id"]
            )

    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(_enrich_player, blue + red))

    bans = [
        {"champion_id": b.get("championId", 0), "team_id": b.get("teamId", 0)}
        for b in spectator_data.get("bannedChampions", [])
    ]

    features = _build_live_features(ddragon, db, blue, red, bans)
    if not features:
        raise ValueError("Could not build features for this game")

    X = pd.DataFrame([features])
    for col in feature_names:
        if col not in X.columns:
            X[col] = 0.0
    X = X[feature_names]

    result = explain_single_match(model, X)

    participants_info = []
    for p in raw:
        champ = ddragon.get_champion(p["champion_id"])
        enr = p.get("_enrichment", {})
        rank = enr.get("rank")
        riot_id = p.get("riotId", "")
        game_name, tag_line = riot_id.split("#", 1) if "#" in riot_id else (riot_id, "")
        participants_info.append(
            {
                "puuid": p["puuid"],
                "riot_id": riot_id,
                "game_name": game_name,
                "tag_line": tag_line,
                "champion_id": p["champion_id"],
                "champion_name": champ["name"]
                if champ
                else f"Champion {p['champion_id']}",
                "team_id": p["team_id"],
                "position": p.get("team_position", "UNKNOWN"),
                "rank": rank,
                "summoner_level": p.get("summoner_level", 0),
            }
        )

    ban_info = []
    for b in spectator_data.get("bannedChampions", []):
        champ = ddragon.get_champion(b.get("championId", 0))
        ban_info.append(
            {
                "champion_id": b.get("championId", 0),
                "champion_name": champ["name"] if champ else "Unknown",
                "team_id": b.get("teamId", 0),
            }
        )

    return {
        "blue_win_probability": result["blue_win_probability"],
        "top_factors": [
            {"feature": name, "impact": float(impact)}
            for name, impact in result["top_factors"]
        ],
        "participants": participants_info,
        "bans": ban_info,
        "game_id": spectator_data.get("gameId"),
        "game_mode": spectator_data.get("gameMode"),
        "game_length_seconds": spectator_data.get("gameLength", 0),
    }
