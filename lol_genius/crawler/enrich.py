from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from lol_genius.api.riot_api import RiotAPI
from lol_genius.crawler.parse import parse_match
from lol_genius.db.queries import MatchDB

log = logging.getLogger(__name__)


def _build_rank_entry(puuid: str, summoner_id: str, entry: dict) -> dict:
    return {
        "puuid": puuid,
        "summoner_id": summoner_id or "",
        "queue_type": "RANKED_SOLO_5x5",
        "tier": entry.get("tier", "UNRANKED"),
        "rank": entry.get("rank", "IV"),
        "league_points": entry.get("leaguePoints", 0),
        "wins": entry.get("wins", 0),
        "losses": entry.get("losses", 0),
        "veteran": 1 if entry.get("veteran", False) else 0,
        "inactive": 1 if entry.get("inactive", False) else 0,
        "fresh_blood": 1 if entry.get("freshBlood", False) else 0,
        "hot_streak": 1 if entry.get("hotStreak", False) else 0,
    }


@dataclass
class EnrichResult:
    puuid: str
    summoner_id: str
    rank_entry: dict | None = None
    league_raw_json: str | None = None
    mastery_records: list[dict] | None = None
    mastery_raw_entries: list[tuple[str, int, str]] | None = None
    recent_stats: dict | None = None
    opportunistic_matches: list[tuple[dict, list, list | None, list | None, str | None]] = field(default_factory=list)


def check_enrich_needed(
    db: MatchDB, puuid: str, summoner_id: str, start_time_ms: int | None = None,
) -> tuple[dict[str, bool], dict | None]:
    needs = {"rank": False, "mastery": False, "stats": False}
    precomputed_stats = None

    if not db.has_recent_rank(puuid):
        needs["rank"] = True
    if not db.has_mastery_data(puuid):
        needs["mastery"] = True
    if not db.has_recent_stats(puuid):
        stats = db.compute_recent_stats_from_db(puuid, start_time_ms=start_time_ms)
        if stats and stats["games_played"] >= 1:
            precomputed_stats = stats
        else:
            needs["stats"] = True

    return needs, precomputed_stats


def fetch_enrichment(
    api: RiotAPI, puuid: str, summoner_id: str, needs: dict[str, bool],
    start_time: int | None = None,
) -> EnrichResult:
    result = EnrichResult(puuid=puuid, summoner_id=summoner_id)

    if needs.get("rank"):
        entries = api.get_league_by_puuid(puuid)
        if entries:
            try:
                result.league_raw_json = json.dumps(entries)
            except Exception as e:
                log.debug(f"Failed to serialize league JSON for {puuid}: {e}")
            for entry in entries:
                if entry.get("queueType") != "RANKED_SOLO_5x5":
                    continue
                result.rank_entry = _build_rank_entry(puuid, summoner_id, entry)
                break

    if needs.get("mastery"):
        entries = api.get_top_masteries(puuid, count=20)
        if entries:
            result.mastery_records = [
                {
                    "puuid": puuid,
                    "champion_id": e.get("championId", 0),
                    "mastery_level": e.get("championLevel", 0),
                    "mastery_points": e.get("championPoints", 0),
                    "last_play_time": e.get("lastPlayTime"),
                    "champion_points_until_next_level": e.get("championPointsUntilNextLevel"),
                }
                for e in entries
            ]
            result.mastery_raw_entries = []
            for e in entries:
                try:
                    result.mastery_raw_entries.append(
                        (puuid, e.get("championId", 0), json.dumps(e))
                    )
                except Exception as exc:
                    log.debug(f"Failed to serialize mastery JSON for {puuid}: {exc}")

    if needs.get("stats"):
        stats = _fetch_recent_stats_via_api(api, puuid, start_time)
        if stats:
            result.opportunistic_matches = stats.pop("_opportunistic_matches", [])
            result.recent_stats = stats

    return result


def write_enrichment(db: MatchDB, result: EnrichResult) -> None:
    if result.league_raw_json:
        try:
            db.insert_league_raw_json(result.puuid, result.league_raw_json)
        except Exception as e:
            log.debug(f"Failed to insert league raw JSON for {result.puuid}: {e}")

    if result.rank_entry:
        db.insert_summoner_rank(result.rank_entry)

    if result.mastery_records:
        db.insert_champion_mastery_batch(result.mastery_records)

    if result.mastery_raw_entries:
        for puuid, champion_id, raw in result.mastery_raw_entries:
            try:
                db.insert_mastery_raw_json(puuid, champion_id, raw)
            except Exception as e:
                log.debug(f"Failed to insert mastery raw JSON for {puuid} champ {champion_id}: {e}")

    if result.recent_stats:
        db.upsert_player_recent_stats(result.recent_stats)

    for match_row, part_rows, bans, objectives, raw_json in result.opportunistic_matches:
        if not db.match_exists(match_row["match_id"]):
            db.insert_match(match_row, part_rows, bans=bans, objectives=objectives, raw_json=raw_json)


def _fetch_recent_stats_via_api(
    api: RiotAPI, puuid: str, start_time: int | None = None,
) -> dict | None:
    match_ids = api.get_match_ids(puuid, count=20, queue=420, start_time=start_time)
    if not match_ids:
        return None

    games = 0
    wins = 0
    total_kills = 0.0
    total_deaths = 0.0
    total_assists = 0.0
    total_cs_per_min = 0.0
    total_vision = 0.0
    total_damage_share = 0.0
    total_wards_placed = 0.0
    total_wards_killed = 0.0
    total_damage_taken = 0.0
    total_gold_spent = 0.0
    total_cc_score = 0.0
    total_heal = 0.0
    total_magic_dmg_share = 0.0
    total_phys_dmg_share = 0.0
    total_multikills = 0.0
    opportunistic_matches: list[tuple[dict, list, list | None, list | None, str | None]] = []

    for mid in match_ids:
        match = api.get_match(mid)
        if not match:
            continue

        parsed = parse_match(match)
        if parsed:
            match_row, part_rows, bans, objectives = parsed
            raw_json = None
            try:
                raw_json = json.dumps(match)
            except Exception as e:
                log.debug(f"Failed to serialize match JSON for {mid}: {e}")
            opportunistic_matches.append((match_row, part_rows, bans, objectives, raw_json))

        info = match.get("info", {})
        duration_min = max(info.get("gameDuration", 1) / 60.0, 1.0)

        team_damage = {}
        player_data = None

        for p in info.get("participants", []):
            tid = p.get("teamId", 0)
            dmg = p.get("totalDamageDealtToChampions", 0)
            team_damage[tid] = team_damage.get(tid, 0) + dmg

            if p.get("puuid") == puuid:
                player_data = p

        if not player_data:
            continue

        games += 1
        if player_data.get("win", False):
            wins += 1

        total_kills += player_data.get("kills", 0)
        total_deaths += player_data.get("deaths", 0)
        total_assists += player_data.get("assists", 0)

        cs = player_data.get("totalMinionsKilled", 0) + player_data.get("neutralMinionsKilled", 0)
        total_cs_per_min += cs / duration_min
        total_vision += player_data.get("visionScore", 0)
        total_wards_placed += player_data.get("wardsPlaced", 0)
        total_wards_killed += player_data.get("wardsKilled", 0)
        total_damage_taken += player_data.get("totalDamageTaken", 0)
        total_gold_spent += player_data.get("goldSpent", 0)
        total_cc_score += player_data.get("timeCCingOthers", 0)
        total_heal += player_data.get("totalHeal", 0)

        player_tid = player_data.get("teamId", 100)
        team_total_dmg = team_damage.get(player_tid, 1)
        if team_total_dmg > 0:
            total_damage_share += player_data.get("totalDamageDealtToChampions", 0) / team_total_dmg

        player_total_dmg = player_data.get("totalDamageDealtToChampions", 0)
        if player_total_dmg > 0:
            total_magic_dmg_share += player_data.get("magicDamageDealtToChampions", 0) / player_total_dmg
            total_phys_dmg_share += player_data.get("physicalDamageDealtToChampions", 0) / player_total_dmg

        total_multikills += (
            player_data.get("doubleKills", 0)
            + player_data.get("tripleKills", 0)
            + player_data.get("quadraKills", 0)
            + player_data.get("pentaKills", 0)
        )

    if games == 0:
        return None

    stats = {
        "puuid": puuid,
        "games_played": games,
        "wins": wins,
        "avg_kills": total_kills / games,
        "avg_deaths": total_deaths / games,
        "avg_assists": total_assists / games,
        "avg_cs_per_min": total_cs_per_min / games,
        "avg_vision": total_vision / games,
        "avg_damage_share": total_damage_share / games,
        "avg_wards_placed": total_wards_placed / games,
        "avg_wards_killed": total_wards_killed / games,
        "avg_damage_taken": total_damage_taken / games,
        "avg_gold_spent": total_gold_spent / games,
        "avg_cc_score": total_cc_score / games,
        "avg_heal_total": total_heal / games,
        "avg_magic_dmg_share": total_magic_dmg_share / games,
        "avg_phys_dmg_share": total_phys_dmg_share / games,
        "avg_multikill_rate": total_multikills / games,
    }
    stats["_opportunistic_matches"] = opportunistic_matches
    return stats


def re_enrich_stale_batch(
    api: RiotAPI, db: MatchDB, stale_puuids: list[dict], start_time: int | None = None,
) -> int:
    refreshed = 0
    for entry in stale_puuids:
        puuid = entry["puuid"]
        summoner_id = entry.get("summoner_id", "")

        needs = {"rank": True, "mastery": False, "stats": False}
        result = fetch_enrichment(api, puuid, summoner_id, needs)
        write_enrichment(db, result)

        start_time_ms = start_time * 1000 if start_time else None
        stats = db.compute_recent_stats_from_db(puuid, start_time_ms=start_time_ms)
        if stats and stats["games_played"] >= 1:
            db.upsert_player_recent_stats(stats)

        refreshed += 1

    return refreshed
