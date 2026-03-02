from lol_genius.crawler.parse import parse_patch, parse_match


def test_parse_patch_standard():
    assert parse_patch("14.10.612.1234") == "14.10"


def test_parse_patch_two_parts():
    assert parse_patch("14.10") == "14.10"


def test_parse_patch_single_part():
    assert parse_patch("14") == "14"


def test_parse_patch_empty():
    assert parse_patch("") == ""


def _make_riot_participant(i):
    team_id = 100 if i < 5 else 200
    win = i < 5
    return {
        "puuid": f"puuid_{i}",
        "summonerId": f"summ_{i}",
        "teamId": team_id,
        "win": win,
        "championId": 100 + i,
        "championName": f"Champ{i}",
        "teamPosition": ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"][i % 5],
        "kills": 5 + i,
        "deaths": 2,
        "assists": 7,
        "totalDamageDealtToChampions": 20000,
        "totalMinionsKilled": 150,
        "neutralMinionsKilled": 30,
        "visionScore": 25,
        "goldEarned": 12000,
        "summoner1Id": 4,
        "summoner2Id": 14,
        "summonerLevel": 200,
        "perks": {
            "styles": [
                {"style": 8100, "selections": [{"perk": 8112}, {"perk": 8126}]},
                {"style": 8300, "selections": [{"perk": 8304}]},
            ],
            "statPerks": {"offense": 5008, "flex": 5008, "defense": 5002},
        },
        "magicDamageDealtToChampions": 8000,
        "physicalDamageDealtToChampions": 10000,
        "trueDamageDealtToChampions": 2000,
        "totalDamageTaken": 15000,
        "damageSelfMitigated": 8000,
        "wardsPlaced": 10,
        "wardsKilled": 3,
        "detectorWardsPlaced": 2,
        "goldSpent": 11000,
        "timeCCingOthers": 20,
        "totalHeal": 5000,
        "totalHealsOnTeammates": 1000,
        "doubleKills": 1,
        "tripleKills": 0,
        "quadraKills": 0,
        "pentaKills": 0,
        "largestKillingSpree": 5,
        "item0": 3071,
        "item1": 3047,
        "item2": 3026,
        "item3": 3053,
        "item4": 3065,
        "item5": 3075,
        "item6": 3340,
        "champLevel": 16,
    }


def _make_riot_match(participants=None, blue_win=True):
    if participants is None:
        participants = [_make_riot_participant(i) for i in range(10)]
    blue_team_win = blue_win
    return {
        "metadata": {
            "matchId": "NA1_5000",
            "participants": [f"puuid_{i}" for i in range(10)],
        },
        "info": {
            "gameVersion": "14.10.612.1234",
            "gameDuration": 1800,
            "queueId": 420,
            "gameCreation": 1700000000000,
            "gameStartTimestamp": 1700000000000,
            "gameEndTimestamp": 1700001800000,
            "platformId": "NA1",
            "participants": participants,
            "teams": [
                {
                    "teamId": 100,
                    "win": blue_team_win,
                    "bans": [
                        {"championId": 1, "pickTurn": 1},
                        {"championId": 2, "pickTurn": 2},
                    ],
                    "objectives": {
                        "baron": {"first": True, "kills": 2},
                        "dragon": {"first": False, "kills": 1},
                    },
                },
                {
                    "teamId": 200,
                    "win": not blue_team_win,
                    "bans": [
                        {"championId": 3, "pickTurn": 3},
                    ],
                    "objectives": {
                        "baron": {"first": False, "kills": 0},
                        "dragon": {"first": True, "kills": 3},
                    },
                },
            ],
        },
    }


def test_parse_match_happy_path():
    data = _make_riot_match()
    result = parse_match(data)
    assert result is not None

    match_row, participants, bans, objectives = result

    assert match_row["match_id"] == "NA1_5000"
    assert match_row["patch"] == "14.10"
    assert match_row["blue_win"] == 1
    assert match_row["game_creation"] == 1700000000000
    assert match_row["game_duration"] == 1800
    assert match_row["game_start_timestamp"] == 1700000000000
    assert match_row["game_end_timestamp"] == 1700001800000
    assert match_row["platform_id"] == "NA1"
    assert match_row["queue_id"] == 420

    assert len(participants) == 10

    p0 = participants[0]
    assert p0["puuid"] == "puuid_0"
    assert p0["champion_id"] == 100
    assert p0["team_id"] == 100
    assert p0["win"] == 1
    assert p0["perks_keystone"] == 8112
    assert p0["perks_primary_style"] == 8100
    assert p0["perks_sub_style"] == 8300
    assert p0["cs"] == 150 + 30
    assert p0["kills"] == 5
    assert p0["summoner1_id"] == 4
    assert p0["summoner2_id"] == 14
    assert p0["champion_level"] == 16
    assert p0["neutral_minions_killed"] == 30
    assert p0["total_minions_killed"] == 150
    assert p0["perks_offense"] == 5008
    assert p0["perks_flex"] == 5008
    assert p0["perks_defense"] == 5002

    assert len(bans) == 3
    blue_bans = [b for b in bans if b["team_id"] == 100]
    red_bans = [b for b in bans if b["team_id"] == 200]
    assert len(blue_bans) == 2
    assert len(red_bans) == 1
    assert blue_bans[0]["champion_id"] == 1
    assert blue_bans[0]["pick_turn"] == 1

    assert len(objectives) == 4
    blue_baron = [
        o for o in objectives if o["team_id"] == 100 and o["objective"] == "baron"
    ][0]
    assert blue_baron["first"] == 1
    assert blue_baron["kills"] == 2


def test_parse_match_blue_win_false():
    participants = [_make_riot_participant(i) for i in range(10)]
    for p in participants:
        p["win"] = p["teamId"] == 200

    data = _make_riot_match(participants=participants, blue_win=False)
    result = parse_match(data)
    assert result is not None
    assert result[0]["blue_win"] == 0


def test_parse_match_empty_perks():
    participants = [_make_riot_participant(i) for i in range(10)]
    participants[0]["perks"] = {}

    data = _make_riot_match(participants=participants)
    result = parse_match(data)
    assert result is not None
    p0 = result[1][0]
    assert p0["perks_keystone"] == 0
    assert p0["perks_primary_style"] == 0
    assert p0["perks_sub_style"] == 0
    assert p0["perks_offense"] == 0
    assert p0["perks_flex"] == 0
    assert p0["perks_defense"] == 0


def test_parse_match_missing_match_id():
    data = {
        "metadata": {},
        "info": {"participants": [_make_riot_participant(i) for i in range(10)]},
    }
    assert parse_match(data) is None


def test_parse_match_wrong_participant_count():
    data = _make_riot_match(participants=[_make_riot_participant(i) for i in range(9)])
    assert parse_match(data) is None
