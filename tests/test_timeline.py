from __future__ import annotations

import pytest

from lol_genius.features.timeline import LIVE_FEATURE_NAMES, SNAPSHOT_SECONDS
from lol_genius.predict.live_client import (
    _snap_to_snapshot,
    build_live_features,
    parse_live_client_data,
)


def _make_live_client_data(
    game_time: float = 600.0,
    blue_kills: int = 3,
    red_kills: int = 1,
    blue_cs: int = 120,
    red_cs: int = 100,
    events: list | None = None,
) -> dict:
    players = [
        {
            "summonerName": f"Blue{i}",
            "riotId": f"Blue{i}#NA1",
            "team": "ORDER",
            "scores": {"kills": blue_kills // 5, "creepScore": blue_cs // 5},
        }
        for i in range(5)
    ] + [
        {
            "summonerName": f"Red{i}",
            "riotId": f"Red{i}#NA1",
            "team": "CHAOS",
            "scores": {"kills": red_kills // 5, "creepScore": red_cs // 5},
        }
        for i in range(5)
    ]
    return {
        "allPlayers": players,
        "events": {"Events": events or []},
        "gameData": {"gameTime": game_time, "gameId": 12345},
    }


def _make_game_state(**overrides) -> dict:
    base = {
        "game_time": 600.0,
        "blue_kills": 3,
        "red_kills": 1,
        "kill_diff": 2,
        "blue_cs": 120,
        "red_cs": 100,
        "cs_diff": 20,
        "blue_towers": 1,
        "red_towers": 0,
        "tower_diff": 1,
        "blue_dragons": 1,
        "red_dragons": 0,
        "dragon_diff": 1,
        "blue_barons": 0,
        "red_barons": 0,
        "baron_diff": 0,
        "blue_heralds": 1,
        "red_heralds": 0,
        "blue_inhibitors": 0,
        "red_inhibitors": 0,
        "inhibitor_diff": 0,
        "blue_elder": 0,
        "red_elder": 0,
        "elder_diff": 0,
        "first_blood_blue": 1,
        "first_tower_blue": 1,
        "first_dragon_blue": 1,
    }
    base.update(overrides)
    return base


class TestParseClientData:
    def test_basic(self):
        data = _make_live_client_data(game_time=450.0, blue_kills=10, red_kills=5)
        result = parse_live_client_data(data)
        assert result["game_time"] == 450.0
        assert result["blue_kills"] == 10
        assert result["red_kills"] == 5
        assert result["kill_diff"] == 5
        assert result["blue_cs"] == 120
        assert result["red_cs"] == 100

    def test_elder_dragon(self):
        events = [
            {"EventName": "DragonKill", "KillerName": "Blue0", "DragonType": "Elder"},
            {"EventName": "DragonKill", "KillerName": "Red0", "DragonType": "Infernal"},
        ]
        data = _make_live_client_data(events=events)
        result = parse_live_client_data(data)
        assert result["blue_elder"] == 1
        assert result["red_elder"] == 0
        assert result["blue_dragons"] == 0
        assert result["red_dragons"] == 1


class TestBuildLiveFeatures:
    def test_count_and_names(self):
        state = _make_game_state()
        features = build_live_features(state)
        assert set(features.keys()) == set(LIVE_FEATURE_NAMES)
        assert len(features) == len(LIVE_FEATURE_NAMES)

    def test_defaults(self):
        state = _make_game_state()
        features = build_live_features(state)
        assert features["pregame_blue_win_prob"] == 0.5

    def test_pregame_prob_passed(self):
        state = _make_game_state()
        features = build_live_features(state, pregame_win_prob=0.65)
        assert features["pregame_blue_win_prob"] == 0.65

    def test_scaling_interaction(self):
        state = _make_game_state(game_time=900.0)
        summary = {"scaling_score_diff": 2.0}
        features = build_live_features(state, pregame_summary=summary)
        assert features["scaling_advantage_realized"] == pytest.approx(2.0 * (900.0 / 1800.0))
        expected = 2.0 * max(0.0, 1.0 - 900.0 / 1500.0)
        assert features["early_game_window_closing"] == pytest.approx(expected)

    def test_snapshot_uses_raw_time_for_rates(self):
        state = _make_game_state(game_time=750.0, kill_diff=6)
        features = build_live_features(state)
        assert features["game_time_seconds"] == _snap_to_snapshot(750.0)
        assert features["kill_rate_diff"] == pytest.approx(6 / (750.0 / 60.0))

    def test_momentum_deltas_with_prev_diffs(self):
        state = _make_game_state(kill_diff=5, cs_diff=30, tower_diff=2)
        prev = {"kill_diff": 3, "cs_diff": 20, "tower_diff": 1}
        features = build_live_features(state, prev_diffs=prev)
        assert features["kill_diff_delta"] == 2
        assert features["cs_diff_delta"] == 10
        assert features["tower_diff_delta"] == 1


class TestLeadErosionSymmetric:
    def test_blue_lead_erosion(self):
        state = _make_game_state(kill_diff=3, tower_diff=2)
        features = build_live_features(state, peak_kill_diff=5.0, peak_tower_diff=3.0)
        assert features["kill_lead_erosion"] == pytest.approx(5.0 - 3.0)
        assert features["tower_lead_erosion"] == pytest.approx(3.0 - 2.0)

    def test_red_lead_erosion(self):
        state = _make_game_state(kill_diff=-2, tower_diff=-1)
        features = build_live_features(state, peak_kill_diff=5.0, peak_tower_diff=3.0)
        assert features["kill_lead_erosion"] == pytest.approx(5.0 - 2.0)
        assert features["tower_lead_erosion"] == pytest.approx(3.0 - 1.0)

    def test_no_erosion_at_peak(self):
        state = _make_game_state(kill_diff=-5)
        features = build_live_features(state, peak_kill_diff=5.0)
        assert features["kill_lead_erosion"] == pytest.approx(0.0)


class TestGamePhaseIndicators:
    def test_early_phase(self):
        state = _make_game_state(game_time=600.0)
        features = build_live_features(state)
        assert features["game_phase_early"] == 1.0
        assert features["game_phase_mid"] == 0.0
        assert features["game_phase_late"] == 0.0

    def test_early_boundary(self):
        state = _make_game_state(game_time=900.0)
        features = build_live_features(state)
        assert features["game_phase_early"] == 1.0
        assert features["game_phase_mid"] == 0.0

    def test_mid_phase(self):
        state = _make_game_state(game_time=1200.0)
        features = build_live_features(state)
        assert features["game_phase_early"] == 0.0
        assert features["game_phase_mid"] == 1.0
        assert features["game_phase_late"] == 0.0

    def test_late_phase(self):
        state = _make_game_state(game_time=2000.0)
        features = build_live_features(state)
        assert features["game_phase_early"] == 0.0
        assert features["game_phase_mid"] == 0.0
        assert features["game_phase_late"] == 1.0

    def test_mid_boundary(self):
        state = _make_game_state(game_time=1500.0)
        features = build_live_features(state)
        assert features["game_phase_mid"] == 1.0
        assert features["game_phase_late"] == 0.0


class TestObjectiveDensity:
    def test_basic(self):
        state = _make_game_state(
            game_time=600.0,
            blue_dragons=1, red_dragons=0,
            blue_barons=0, red_barons=0,
            blue_heralds=1, red_heralds=0,
        )
        features = build_live_features(state)
        assert features["objective_density"] == pytest.approx(2.0 / 10.0)

    def test_many_objectives(self):
        state = _make_game_state(
            game_time=1800.0,
            blue_dragons=3, red_dragons=2,
            blue_barons=1, red_barons=0,
            blue_heralds=1, red_heralds=1,
        )
        features = build_live_features(state)
        total = 3 + 2 + 1 + 0 + 1 + 1
        assert features["objective_density"] == pytest.approx(total / 30.0)


class TestExtractTimelineSnapshots:
    def test_basic_mock(self):
        frames = [{"timestamp": s * 1000} for s in range(0, 3001, 60)]
        assert len(frames) == 51

    def test_short_game(self):
        frames = [{"timestamp": s * 1000} for s in range(0, 400, 60)]
        assert len(frames) == 7
        matching = [s for s in SNAPSHOT_SECONDS if s <= 360]
        assert matching == [300]


class TestSnapToSnapshot:
    def test_exact(self):
        assert _snap_to_snapshot(600) == 600

    def test_between(self):
        assert _snap_to_snapshot(750) == 600

    def test_near_next(self):
        assert _snap_to_snapshot(890) == 900
