from __future__ import annotations

import logging

log = logging.getLogger(__name__)

BLUE_TEAM_ID = 100
RED_TEAM_ID = 200
SNAPSHOT_SECONDS = [300, 600, 900, 1200, 1500, 1800, 2100, 2400, 2700, 3000]


def build_timelines_from_db(db) -> int:
    """Populate match_timelines from existing participants + match_team_objectives data.

    Creates one end-of-game snapshot per match using game_duration as snapshot_seconds.
    Requires no additional API calls.
    """
    rows = db._execute(
        f"""
        SELECT
            m.match_id,
            m.game_duration AS snapshot_seconds,
            SUM(CASE WHEN p.team_id = {BLUE_TEAM_ID} THEN p.gold_earned ELSE 0 END)  AS blue_gold,
            SUM(CASE WHEN p.team_id = {RED_TEAM_ID} THEN p.gold_earned ELSE 0 END)  AS red_gold,
            SUM(CASE WHEN p.team_id = {BLUE_TEAM_ID} THEN p.kills       ELSE 0 END)  AS blue_kills,
            SUM(CASE WHEN p.team_id = {RED_TEAM_ID} THEN p.kills       ELSE 0 END)  AS red_kills
        FROM matches m
        JOIN participants p ON m.match_id = p.match_id
        JOIN match_enrichment_status e ON m.match_id = e.match_id
        WHERE e.enriched = 1
          AND NOT EXISTS (
              SELECT 1 FROM match_timelines t WHERE t.match_id = m.match_id
          )
        GROUP BY m.match_id, m.game_duration
        """
    ).fetchall()

    if not rows:
        log.info("No matches to process for timeline synthesis")
        return 0

    obj_rows = db._execute(
        """
        SELECT match_id, team_id, objective, first, kills
        FROM match_team_objectives
        WHERE objective IN ('dragon', 'baron', 'riftHerald', 'champion', 'tower')
        """
    ).fetchall()

    obj_map: dict[str, dict] = {}
    for r in obj_rows:
        mid = r["match_id"]
        if mid not in obj_map:
            obj_map[mid] = {}
        key = f"{r['team_id']}_{r['objective']}"
        obj_map[mid][key] = {"first": r["first"], "kills": r["kills"]}

    saved = 0
    db.begin_batch()
    try:
        for r in rows:
            mid = r["match_id"]
            objs = obj_map.get(mid, {})

            snapshot = {
                "snapshot_seconds": r["snapshot_seconds"],
                "blue_gold": r["blue_gold"] or 0,
                "red_gold": r["red_gold"] or 0,
                "blue_kills": r["blue_kills"] or 0,
                "red_kills": r["red_kills"] or 0,
                "blue_towers": objs.get("100_tower", {}).get("kills", 0),
                "red_towers": objs.get("200_tower", {}).get("kills", 0),
                "blue_dragons": objs.get("100_dragon", {}).get("kills", 0),
                "red_dragons": objs.get("200_dragon", {}).get("kills", 0),
                "blue_barons": objs.get("100_baron", {}).get("kills", 0),
                "red_barons": objs.get("200_baron", {}).get("kills", 0),
                "blue_heralds": objs.get("100_riftHerald", {}).get("kills", 0),
                "red_heralds": objs.get("200_riftHerald", {}).get("kills", 0),
                "first_blood_blue": objs.get("100_champion", {}).get("first", 0),
                "first_tower_blue": objs.get("100_tower", {}).get("first", 0),
                "first_dragon_blue": objs.get("100_dragon", {}).get("first", 0),
            }
            db.save_timeline_snapshots(mid, [snapshot])
            saved += 1

        db.flush()
    finally:
        db.end_batch()

    log.info(f"Synthesized {saved} end-of-game timeline snapshots from DB")
    return saved


def _participant_team(participant_id: int) -> int:
    return BLUE_TEAM_ID if participant_id <= 5 else RED_TEAM_ID


def extract_timeline_snapshots(timeline_data: dict) -> list[dict]:
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

        blue_gold = 0
        red_gold = 0
        for pid_str, pframe in snap_frame.get("participantFrames", {}).items():
            pid = int(pid_str)
            gold = pframe.get("totalGold", 0)
            if pid <= 5:
                blue_gold += gold
            else:
                red_gold += gold

        blue_kills = red_kills = 0
        blue_towers = red_towers = 0
        blue_dragons = red_dragons = 0
        blue_barons = red_barons = 0
        blue_heralds = red_heralds = 0
        first_blood_blue = first_tower_blue = first_dragon_blue = 0
        first_blood_set = first_tower_set = first_dragon_set = False

        for event in all_events:
            if event["timestamp"] > snap_ms:
                break

            etype = event.get("type", "")

            if etype == "CHAMPION_KILL":
                killer_id = event.get("killerId", 0)
                if killer_id > 0:
                    if _participant_team(killer_id) == 100:
                        blue_kills += 1
                    else:
                        red_kills += 1
                    if not first_blood_set:
                        first_blood_set = True
                        first_blood_blue = (
                            1 if _participant_team(killer_id) == 100 else 0
                        )

            elif etype == "BUILDING_KILL":
                killer_id = event.get("killerId", 0)
                if killer_id > 0:
                    killer_team = _participant_team(killer_id)
                else:
                    team_id = event.get("teamId", 0)
                    killer_team = 200 if team_id == 100 else 100
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

        snapshots.append(
            {
                "snapshot_seconds": snap_sec,
                "blue_gold": blue_gold,
                "red_gold": red_gold,
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
                "first_blood_blue": first_blood_blue,
                "first_tower_blue": first_tower_blue,
                "first_dragon_blue": first_dragon_blue,
            }
        )

    return snapshots


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
            snapshots = extract_timeline_snapshots(timeline)
            if snapshots:
                db.save_timeline_snapshots(match_id, snapshots)
                success += 1
                if limit is not None and success >= limit:
                    break
        except Exception as e:
            log.warning(f"Failed to fetch timeline for {match_id}: {e}")

    log.info(f"Timeline fetch complete: {success}/{len(match_ids)} succeeded")
