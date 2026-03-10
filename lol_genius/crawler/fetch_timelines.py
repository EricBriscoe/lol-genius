from __future__ import annotations

import json
import logging

from lol_genius.features.timeline import SNAPSHOT_SECONDS

log = logging.getLogger(__name__)

BLUE_TEAM_ID = 100
RED_TEAM_ID = 200

_POSITION_ABBREV = {
    "TOP": "top",
    "JUNGLE": "jg",
    "MIDDLE": "mid",
    "BOTTOM": "bot",
    "UTILITY": "sup",
}

_POSITIONS = list(_POSITION_ABBREV.values())
_SIDES = ["blue", "red"]


def _participant_team(participant_id: int) -> int:
    return BLUE_TEAM_ID if participant_id <= 5 else RED_TEAM_ID


def _empty_per_role() -> dict:
    out = {}
    for side in _SIDES:
        for pos in _POSITIONS:
            out[f"{side}_{pos}_cs"] = 0
            out[f"{side}_{pos}_level"] = 1
            out[f"{side}_{pos}_kills"] = 0
    return out


def extract_timeline_snapshots(
    timeline_data: dict,
    position_map: dict[int, tuple[str, str]] | None = None,
) -> list[dict]:
    frames = timeline_data.get("info", {}).get("frames", [])
    if not frames:
        return []
    frames.sort(key=lambda f: f.get("timestamp", 0))

    all_events: list[dict] = []
    for frame in frames:
        all_events.extend(frame.get("events", []))

    snapshots = []
    for snap_sec in SNAPSHOT_SECONDS:
        snap_ms = snap_sec * 1000

        snap_frame = None
        for frame in frames:
            if frame["timestamp"] <= snap_ms:
                snap_frame = frame
            else:
                break

        if snap_frame is None:
            break

        blue_gold = red_gold = 0
        blue_cs = red_cs = 0
        blue_levels: list[int] = []
        red_levels: list[int] = []
        per_role = _empty_per_role()

        for pid_str, pframe in snap_frame.get("participantFrames", {}).items():
            pid = int(pid_str)
            gold = pframe.get("totalGold", 0)
            cs = pframe.get("minionsKilled", 0) + pframe.get("neutralMinionsKilled", 0)
            level = pframe.get("level", 1)
            if pid <= 5:
                blue_gold += gold
                blue_cs += cs
                blue_levels.append(level)
            else:
                red_gold += gold
                red_cs += cs
                red_levels.append(level)

            if position_map and pid in position_map:
                side, pos = position_map[pid]
                per_role[f"{side}_{pos}_cs"] = cs
                per_role[f"{side}_{pos}_level"] = level

        blue_kills = red_kills = 0
        blue_towers = red_towers = 0
        blue_dragons = red_dragons = 0
        blue_barons = red_barons = 0
        blue_heralds = red_heralds = 0
        blue_inhibitors = red_inhibitors = 0
        blue_elder = red_elder = 0
        first_blood_blue = first_tower_blue = first_dragon_blue = 0
        first_blood_set = first_tower_set = first_dragon_set = False
        kills_by_pid: dict[int, int] = {}

        for event in all_events:
            if event["timestamp"] > snap_ms:
                break

            etype = event.get("type", "")

            if etype == "CHAMPION_KILL":
                killer_id = event.get("killerId", 0)
                if killer_id > 0:
                    kills_by_pid[killer_id] = kills_by_pid.get(killer_id, 0) + 1
                    if _participant_team(killer_id) == 100:
                        blue_kills += 1
                    else:
                        red_kills += 1
                    if not first_blood_set:
                        first_blood_set = True
                        first_blood_blue = 1 if _participant_team(killer_id) == 100 else 0

            elif etype == "BUILDING_KILL":
                killer_id = event.get("killerId", 0)
                if killer_id > 0:
                    killer_team = _participant_team(killer_id)
                else:
                    team_id = event.get("teamId", 0)
                    killer_team = 200 if team_id == 100 else 100
                btype = event.get("buildingType", "")
                if btype == "INHIBITOR_BUILDING":
                    if killer_team == 100:
                        blue_inhibitors += 1
                    else:
                        red_inhibitors += 1
                else:
                    if killer_team == 100:
                        blue_towers += 1
                        if not first_tower_set:
                            first_tower_set = True
                            first_tower_blue = 1
                    else:
                        red_towers += 1
                        if not first_tower_set:
                            first_tower_set = True
                            first_tower_blue = 0

            elif etype == "ELITE_MONSTER_KILL":
                monster = event.get("monsterType", "")
                killer_team = event.get("killerTeamId", 0)
                if monster == "DRAGON":
                    sub = event.get("monsterSubType", "")
                    if sub == "ELDER_DRAGON":
                        if killer_team == 100:
                            blue_elder += 1
                        else:
                            red_elder += 1
                    else:
                        if killer_team == 100:
                            blue_dragons += 1
                            if not first_dragon_set:
                                first_dragon_set = True
                                first_dragon_blue = 1
                        else:
                            red_dragons += 1
                            if not first_dragon_set:
                                first_dragon_set = True
                                first_dragon_blue = 0
                elif monster == "BARON_NASHOR":
                    if killer_team == 100:
                        blue_barons += 1
                    else:
                        red_barons += 1
                elif monster == "RIFTHERALD":
                    if killer_team == 100:
                        blue_heralds += 1
                    else:
                        red_heralds += 1

        if position_map:
            for pid, k in kills_by_pid.items():
                if pid in position_map:
                    side, pos = position_map[pid]
                    per_role[f"{side}_{pos}_kills"] = k

        snapshots.append(
            {
                "snapshot_seconds": snap_sec,
                "blue_gold": blue_gold,
                "red_gold": red_gold,
                "blue_cs": blue_cs,
                "red_cs": red_cs,
                "blue_avg_level": sum(blue_levels) / len(blue_levels) if blue_levels else 1.0,
                "red_avg_level": sum(red_levels) / len(red_levels) if red_levels else 1.0,
                "blue_max_level": max(blue_levels) if blue_levels else 1,
                "red_max_level": max(red_levels) if red_levels else 1,
                "blue_kills": blue_kills,
                "red_kills": red_kills,
                "blue_towers": blue_towers,
                "red_towers": red_towers,
                "blue_dragons": blue_dragons,
                "red_dragons": red_dragons,
                "blue_barons": blue_barons,
                "red_barons": red_barons,
                "blue_heralds": blue_heralds,
                "red_heralds": red_heralds,
                "blue_inhibitors": blue_inhibitors,
                "red_inhibitors": red_inhibitors,
                "blue_elder": blue_elder,
                "red_elder": red_elder,
                "first_blood_blue": first_blood_blue,
                "first_tower_blue": first_tower_blue,
                "first_dragon_blue": first_dragon_blue,
                **per_role,
            }
        )

    return snapshots


def _build_position_map(
    db, match_id: str, timeline_data: dict
) -> dict[int, tuple[str, str]] | None:
    tl_participants = timeline_data.get("info", {}).get("participants", [])
    if not tl_participants:
        return None
    puuid_to_pid = {p["puuid"]: p["participantId"] for p in tl_participants if "puuid" in p}
    if not puuid_to_pid:
        return None

    db_rows = db.get_participants_for_match(match_id)
    if not db_rows:
        return None

    pid_map: dict[int, tuple[str, str]] = {}
    for row in db_rows:
        puuid = row.get("puuid")
        pos_raw = row.get("team_position", "")
        pos = _POSITION_ABBREV.get(pos_raw)
        if not puuid or pos is None:
            continue
        pid = puuid_to_pid.get(puuid)
        if pid is None:
            continue
        side = "blue" if pid <= 5 else "red"
        pid_map[pid] = (side, pos)
    return pid_map if pid_map else None


def _process_timeline(db, match_id: str, timeline: dict) -> bool:
    position_map = _build_position_map(db, match_id, timeline)
    snapshots = extract_timeline_snapshots(timeline, position_map)
    if not snapshots:
        return False
    db.save_timeline_snapshots(match_id, snapshots)
    return True


def fetch_match_timelines(api, db, limit: int | None = None) -> None:
    match_ids = db.get_match_ids_without_timelines()
    log.info(f"Fetching timelines for {len(match_ids)} matches")

    success = 0
    for match_id in match_ids:
        try:
            timeline = api.get_match_timeline(match_id)
            if not timeline:
                log.warning(f"No timeline data for {match_id}")
                continue
            db.insert_timeline_raw_json(match_id, json.dumps(timeline))
            if _process_timeline(db, match_id, timeline):
                success += 1
                if limit is not None and success >= limit:
                    break
        except Exception as e:
            log.warning(f"Failed to fetch timeline for {match_id}: {e}")

    log.info(f"Timeline fetch complete: {success}/{len(match_ids)} succeeded")


def backfill_timelines_from_raw(db) -> None:
    rows = db.get_all_timeline_raw_json()
    log.info(f"Backfilling timelines from {len(rows)} stored raw JSONs")

    success = 0
    for match_id, timeline in rows:
        try:
            if _process_timeline(db, match_id, timeline):
                success += 1
        except Exception as e:
            log.warning(f"Failed to backfill timeline for {match_id}: {e}")

    log.info(f"Backfill complete: {success}/{len(rows)} succeeded")
