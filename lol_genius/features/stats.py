from __future__ import annotations


def normalize_api_match_row(puuid: str, match: dict) -> dict | None:
    info = match.get("info", {})
    participants = info.get("participants", [])

    player = None
    team_id = None
    for p in participants:
        if p.get("puuid") == puuid:
            player = p
            team_id = p.get("teamId", 0)
            break

    if not player:
        return None

    team_total_dmg = sum(
        pp.get("totalDamageDealtToChampions", 0)
        for pp in participants
        if pp.get("teamId") == team_id
    )

    return {
        "win": player.get("win", False),
        "kills": player.get("kills", 0),
        "deaths": player.get("deaths", 0),
        "assists": player.get("assists", 0),
        "total_damage": player.get("totalDamageDealtToChampions", 0),
        "cs": player.get("totalMinionsKilled", 0) + player.get("neutralMinionsKilled", 0),
        "vision_score": player.get("visionScore", 0),
        "game_duration": info.get("gameDuration", 1),
        "team_total_dmg": team_total_dmg,
        "wards_placed": player.get("wardsPlaced", 0),
        "wards_killed": player.get("wardsKilled", 0),
        "total_damage_taken": player.get("totalDamageTaken", 0),
        "gold_spent": player.get("goldSpent", 0),
        "time_ccing_others": player.get("timeCCingOthers", 0),
        "total_heal": player.get("totalHeal", 0),
        "magic_damage_to_champions": player.get("magicDamageDealtToChampions", 0),
        "physical_damage_to_champions": player.get("physicalDamageDealtToChampions", 0),
        "double_kills": player.get("doubleKills", 0),
        "triple_kills": player.get("tripleKills", 0),
        "quadra_kills": player.get("quadraKills", 0),
        "penta_kills": player.get("pentaKills", 0),
    }


def aggregate_recent_stats(puuid: str, rows: list[dict]) -> dict | None:
    if not rows:
        return None

    games = len(rows)
    wins = sum(1 for r in rows if r["win"])
    total_kills = sum(r["kills"] or 0 for r in rows)
    total_deaths = sum(r["deaths"] or 0 for r in rows)
    total_assists = sum(r["assists"] or 0 for r in rows)
    total_vision = sum(r["vision_score"] or 0 for r in rows)
    total_wards_placed = sum(r["wards_placed"] or 0 for r in rows)
    total_wards_killed = sum(r["wards_killed"] or 0 for r in rows)
    total_damage_taken = sum(r["total_damage_taken"] or 0 for r in rows)
    total_gold_spent = sum(r["gold_spent"] or 0 for r in rows)
    total_cc_score = sum(r["time_ccing_others"] or 0 for r in rows)
    total_heal = sum(r["total_heal"] or 0 for r in rows)

    total_cs_per_min = 0.0
    total_damage_share = 0.0
    total_magic_dmg_share = 0.0
    total_phys_dmg_share = 0.0
    total_multikills = 0

    for r in rows:
        dur_min = max((r["game_duration"] or 1) / 60.0, 1.0)
        total_cs_per_min += (r["cs"] or 0) / dur_min

        team_total = r.get("team_total_dmg", 0) or 0
        if team_total > 0:
            total_damage_share += (r["total_damage"] or 0) / team_total

        player_total_dmg = r["total_damage"] or 0
        if player_total_dmg > 0:
            total_magic_dmg_share += (r["magic_damage_to_champions"] or 0) / player_total_dmg
            total_phys_dmg_share += (r["physical_damage_to_champions"] or 0) / player_total_dmg

        total_multikills += (
            (r["double_kills"] or 0)
            + (r["triple_kills"] or 0)
            + (r["quadra_kills"] or 0)
            + (r["penta_kills"] or 0)
        )

    kda_per_game = [
        ((r["kills"] or 0) + (r["assists"] or 0)) / max(r["deaths"] or 1, 1) for r in rows
    ]

    return {
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
        "kda_per_game": kda_per_game,
    }
