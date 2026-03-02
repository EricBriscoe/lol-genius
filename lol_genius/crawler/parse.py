from __future__ import annotations


def parse_patch(game_version: str) -> str:
    parts = game_version.split(".")
    return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else game_version


def parse_match(
    match_data: dict,
) -> tuple[dict, list[dict], list[dict], list[dict]] | None:
    info = match_data.get("info", {})
    metadata = match_data.get("metadata", {})

    match_id = metadata.get("matchId")
    if not match_id:
        return None

    game_version = info.get("gameVersion", "")
    patch = parse_patch(game_version)

    blue_win = 0
    participants_data = []

    for p in info.get("participants", []):
        team_id = p.get("teamId", 0)
        win = 1 if p.get("win", False) else 0
        if team_id == 100 and win:
            blue_win = 1

        perks = p.get("perks", {})
        styles = perks.get("styles", [])
        primary_style = styles[0] if len(styles) > 0 else {}
        sub_style = styles[1] if len(styles) > 1 else {}
        primary_selections = primary_style.get("selections", [])
        keystone = primary_selections[0].get("perk", 0) if primary_selections else 0

        stat_perks = perks.get("statPerks", {})

        participants_data.append(
            {
                "match_id": match_id,
                "puuid": p.get("puuid", ""),
                "summoner_id": p.get("summonerId", ""),
                "team_id": team_id,
                "champion_id": p.get("championId", 0),
                "champion_name": p.get("championName", ""),
                "team_position": p.get("teamPosition", ""),
                "win": win,
                "kills": p.get("kills", 0),
                "deaths": p.get("deaths", 0),
                "assists": p.get("assists", 0),
                "total_damage": p.get("totalDamageDealtToChampions", 0),
                "cs": p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0),
                "vision_score": p.get("visionScore", 0),
                "gold_earned": p.get("goldEarned", 0),
                "summoner1_id": p.get("summoner1Id", 0),
                "summoner2_id": p.get("summoner2Id", 0),
                "summoner_level": p.get("summonerLevel", 0),
                "perks_primary_style": primary_style.get("style", 0),
                "perks_sub_style": sub_style.get("style", 0),
                "perks_keystone": keystone,
                "perks_offense": stat_perks.get("offense", 0),
                "perks_flex": stat_perks.get("flex", 0),
                "perks_defense": stat_perks.get("defense", 0),
                "magic_damage_to_champions": p.get("magicDamageDealtToChampions", 0),
                "physical_damage_to_champions": p.get(
                    "physicalDamageDealtToChampions", 0
                ),
                "true_damage_to_champions": p.get("trueDamageDealtToChampions", 0),
                "total_damage_taken": p.get("totalDamageTaken", 0),
                "damage_self_mitigated": p.get("damageSelfMitigated", 0),
                "wards_placed": p.get("wardsPlaced", 0),
                "wards_killed": p.get("wardsKilled", 0),
                "detector_wards_placed": p.get("detectorWardsPlaced", 0),
                "gold_spent": p.get("goldSpent", 0),
                "time_ccing_others": p.get("timeCCingOthers", 0),
                "total_heal": p.get("totalHeal", 0),
                "total_heals_on_teammates": p.get("totalHealsOnTeammates", 0),
                "double_kills": p.get("doubleKills", 0),
                "triple_kills": p.get("tripleKills", 0),
                "quadra_kills": p.get("quadraKills", 0),
                "penta_kills": p.get("pentaKills", 0),
                "largest_killing_spree": p.get("largestKillingSpree", 0),
                "item0": p.get("item0", 0),
                "item1": p.get("item1", 0),
                "item2": p.get("item2", 0),
                "item3": p.get("item3", 0),
                "item4": p.get("item4", 0),
                "item5": p.get("item5", 0),
                "item6": p.get("item6", 0),
                "neutral_minions_killed": p.get("neutralMinionsKilled", 0),
                "total_minions_killed": p.get("totalMinionsKilled", 0),
                "champion_level": p.get("champLevel", 0),
            }
        )

    if len(participants_data) != 10:
        return None

    bans_data = []
    objectives_data = []
    for team in info.get("teams", []):
        tid = team.get("teamId", 0)
        for ban in team.get("bans", []):
            bans_data.append(
                {
                    "match_id": match_id,
                    "team_id": tid,
                    "champion_id": ban.get("championId", 0),
                    "pick_turn": ban.get("pickTurn", 0),
                }
            )
        for obj_name, obj_val in team.get("objectives", {}).items():
            objectives_data.append(
                {
                    "match_id": match_id,
                    "team_id": tid,
                    "objective": obj_name,
                    "first": 1 if obj_val.get("first", False) else 0,
                    "kills": obj_val.get("kills", 0),
                }
            )

    match_row = {
        "match_id": match_id,
        "game_version": game_version,
        "patch": patch,
        "game_duration": info.get("gameDuration", 0),
        "queue_id": info.get("queueId", 0),
        "blue_win": blue_win,
        "game_creation": info.get("gameCreation", 0),
        "game_start_timestamp": info.get("gameStartTimestamp"),
        "game_end_timestamp": info.get("gameEndTimestamp"),
        "platform_id": info.get("platformId"),
    }

    return match_row, participants_data, bans_data, objectives_data
