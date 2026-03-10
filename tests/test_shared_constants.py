from __future__ import annotations

import json
from pathlib import Path

from lol_genius.features.timeline import (
    LIVE_FEATURE_NAMES,
    SNAPSHOT_SECONDS,
    TIMELINE_FEATURE_NAMES,
)
from lol_genius.predict.live_client import _LIVE_CATEGORY_MAP

SHARED_DIR = Path(__file__).resolve().parents[1] / "shared"

with open(SHARED_DIR / "live-feature-names.json") as _f:
    _FEAT_JSON = json.load(_f)

with open(SHARED_DIR / "shap-categories.json") as _f:
    _SHAP_JSON = json.load(_f)


def _compose_live_features(data: dict) -> list[str]:
    gold = set(data["gold_cols"])
    per_role = [
        f"{pos}_{stat}_diff" for pos in data["positions"] for stat in data["per_role_stats"]
    ]
    return (
        [f for f in data["timeline_feature_names"] if f not in gold]
        + data["pregame_summary_cols"]
        + data["momentum_cols"]
        + data["temporal_cols"]
        + data["level_cols"]
        + data["dragon_soul_cols"]
        + per_role
    )


class TestSharedFeatureNames:
    def test_snapshot_seconds_matches_json(self):
        assert SNAPSHOT_SECONDS == _FEAT_JSON["snapshot_seconds"]

    def test_timeline_features_matches_json(self):
        assert TIMELINE_FEATURE_NAMES == _FEAT_JSON["timeline_feature_names"]

    def test_live_features_exact_ordered_match(self):
        assert LIVE_FEATURE_NAMES == _compose_live_features(_FEAT_JSON)

    def test_live_feature_count(self):
        assert len(LIVE_FEATURE_NAMES) == 72

    def test_no_gold_in_live_features(self):
        gold_cols = set(_FEAT_JSON["gold_cols"])
        for feat in LIVE_FEATURE_NAMES:
            assert feat not in gold_cols


class TestSharedShapCategories:
    def test_category_map_matches_json(self):
        assert _LIVE_CATEGORY_MAP == _SHAP_JSON["live_category_map"]

    def test_all_category_features_exist_in_live(self):
        live_set = set(LIVE_FEATURE_NAMES)
        for cat, features in _LIVE_CATEGORY_MAP.items():
            for feat in features:
                assert feat in live_set, (
                    f"Feature '{feat}' in category '{cat}' not in LIVE_FEATURE_NAMES"
                )

    def test_every_live_feature_has_category_or_excluded(self):
        categorized = set()
        for features in _SHAP_JSON["live_category_map"].values():
            categorized.update(features)
        excluded = set(_SHAP_JSON["excluded_features"])
        for feat in LIVE_FEATURE_NAMES:
            assert feat in categorized or feat in excluded, (
                f"Feature '{feat}' has no SHAP category and is not excluded"
            )

    def test_config_values(self):
        assert _SHAP_JSON["impact_threshold"] == 0.3
        assert _SHAP_JSON["max_groups"] == 5
        assert _SHAP_JSON["narrative_config"]["strong_threshold"] == 5
        assert _SHAP_JSON["narrative_config"]["moderate_threshold"] == 2
