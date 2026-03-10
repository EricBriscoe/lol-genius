from __future__ import annotations

POSITION_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
POSITION_SHORT = {
    "TOP": "top",
    "JUNGLE": "jg",
    "MIDDLE": "mid",
    "BOTTOM": "bot",
    "UTILITY": "sup",
}


def align_by_position(participants: list[dict]) -> dict[str, dict]:
    by_pos = {}
    for p in participants:
        pos = p.get("team_position", "")
        if pos in POSITION_ORDER:
            by_pos[pos] = p
    return by_pos


def extract_draft_features(
    blue_players: dict[str, dict],
    red_players: dict[str, dict],
    blue_player_features: dict[str, dict],
    red_player_features: dict[str, dict],
) -> dict:
    features: dict[str, float] = {}

    for pos in POSITION_ORDER:
        short = POSITION_SHORT[pos]
        bp = blue_player_features.get(pos, {})
        rp = red_player_features.get(pos, {})

        features[f"{short}_rank_diff"] = bp.get("rank_numeric", 12.0) - rp.get("rank_numeric", 12.0)
        features[f"{short}_mastery_diff"] = bp.get("mastery_points", 0) - rp.get(
            "mastery_points", 0
        )
        features[f"{short}_wr_diff"] = bp.get("recent_winrate", 0.5) - rp.get("recent_winrate", 0.5)
        features[f"{short}_champ_wr_diff"] = bp.get("champ_winrate", 0.5) - rp.get(
            "champ_winrate", 0.5
        )
        features[f"{short}_summoner_level_diff"] = bp.get("summoner_level", 0) - rp.get(
            "summoner_level", 0
        )
        features[f"{short}_wr_residual_diff"] = bp.get("winrate_rank_residual", 0) - rp.get(
            "winrate_rank_residual", 0
        )

    return features


DRAFT_FEATURE_NAMES = []
for _pos in POSITION_ORDER:
    _short = POSITION_SHORT[_pos]
    DRAFT_FEATURE_NAMES.extend(
        [
            f"{_short}_rank_diff",
            f"{_short}_mastery_diff",
            f"{_short}_wr_diff",
            f"{_short}_champ_wr_diff",
            f"{_short}_summoner_level_diff",
            f"{_short}_wr_residual_diff",
        ]
    )
