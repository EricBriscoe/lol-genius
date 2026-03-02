from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from lol_genius.api.client import BadRequestError
from lol_genius.api.riot_api import RiotAPI
from lol_genius.crawler.parse import parse_match
from lol_genius.db.queries import MatchDB
from lol_genius.features.stats import aggregate_recent_stats, normalize_api_match_row

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
    opportunistic_matches: list[
        tuple[dict, list, list | None, list | None, str | None]
    ] = field(default_factory=list)
    bad_request: bool = False


def check_enrich_needed(
    db: MatchDB,
    puuid: str,
    summoner_id: str,
    start_time_ms: int | None = None,
) -> tuple[dict[str, bool], dict | None]:
    needs = {"rank": False, "mastery": False, "stats": False}

    if not db.has_recent_rank(puuid):
        needs["rank"] = True
    if not db.has_mastery_data(puuid):
        needs["mastery"] = True

    stats = db.compute_recent_stats_from_db(puuid, start_time_ms=start_time_ms)
    if not stats or stats["games_played"] < 1:
        needs["stats"] = True

    return needs, None


def fetch_enrichment(
    api: RiotAPI,
    puuid: str,
    summoner_id: str,
    needs: dict[str, bool],
    start_time: int | None = None,
) -> EnrichResult:
    result = EnrichResult(puuid=puuid, summoner_id=summoner_id)

    if needs.get("rank"):
        try:
            entries = api.get_league_by_puuid(puuid)
        except BadRequestError:
            log.debug(f"400 Bad Request for league data: {puuid}")
            result.bad_request = True
            entries = None
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
        try:
            entries = api.get_top_masteries(puuid, count=20)
        except BadRequestError:
            log.debug(f"400 Bad Request for mastery data: {puuid}")
            result.bad_request = True
            entries = None
        if entries:
            result.mastery_records = [
                {
                    "puuid": puuid,
                    "champion_id": e.get("championId", 0),
                    "mastery_level": e.get("championLevel", 0),
                    "mastery_points": e.get("championPoints", 0),
                    "last_play_time": e.get("lastPlayTime"),
                    "champion_points_until_next_level": e.get(
                        "championPointsUntilNextLevel"
                    ),
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
                log.debug(
                    f"Failed to insert mastery raw JSON for {puuid} champ {champion_id}: {e}"
                )

    for (
        match_row,
        part_rows,
        bans,
        objectives,
        raw_json,
    ) in result.opportunistic_matches:
        if not db.match_exists(match_row["match_id"]):
            db.insert_match(
                match_row,
                part_rows,
                bans=bans,
                objectives=objectives,
                raw_json=raw_json,
            )


def _fetch_recent_stats_via_api(
    api: RiotAPI,
    puuid: str,
    start_time: int | None = None,
) -> dict | None:
    match_ids = api.get_match_ids(puuid, count=20, queue=420, start_time=start_time)
    if not match_ids:
        return None

    stat_rows: list[dict] = []
    opportunistic_matches: list[
        tuple[dict, list, list | None, list | None, str | None]
    ] = []

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
            opportunistic_matches.append(
                (match_row, part_rows, bans, objectives, raw_json)
            )

        row = normalize_api_match_row(puuid, match)
        if row:
            stat_rows.append(row)

    stats = aggregate_recent_stats(puuid, stat_rows)
    if not stats:
        return None

    stats["_opportunistic_matches"] = opportunistic_matches
    return stats


def re_enrich_stale_batch(
    api: RiotAPI,
    db: MatchDB,
    stale_puuids: list[dict],
) -> int:
    refreshed = 0
    for entry in stale_puuids:
        puuid = entry["puuid"]
        summoner_id = entry.get("summoner_id", "")

        needs = {"rank": True, "mastery": False, "stats": False}
        result = fetch_enrichment(api, puuid, summoner_id, needs)
        write_enrichment(db, result)

        refreshed += 1

    return refreshed
