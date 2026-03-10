"""Standalone SHAP prediction sidecar.

Reads a model path from argv[1] and feature JSON from stdin.
Outputs per-feature SHAP values plus factor analysis as JSON to stdout.
"""

import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import shap
import xgboost as xgb


def _load_shap_config():
    candidates = [
        Path(getattr(sys, "_MEIPASS", "")) / "shared" / "shap-categories.json",
        Path(__file__).resolve().parents[2] / "shared" / "shap-categories.json",
    ]
    for p in candidates:
        if p.is_file():
            with open(p) as f:
                return json.load(f)
    return None


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _build_factor_analysis(
    base_value: float,
    shap_dict: dict[str, float],
    model_type: str,
    config: dict,
) -> dict:
    cat_map = config["live_category_map"]
    excluded = set(config["excluded_features"])
    impact_threshold = config["impact_threshold"]
    max_groups = config["max_groups"]
    narr = config["narrative_config"]

    if model_type == "pregame":
        suffix_rules = config.get("pregame_suffix_rules", [])
        exact_map = config.get("pregame_exact", {})
    else:
        suffix_rules = None
        exact_map = None

    feat_to_cat: dict[str, str] = {}
    for cat, features in cat_map.items():
        for f in features:
            feat_to_cat[f] = cat

    total_shap = sum(shap_dict.values())
    total_log_odds = base_value + total_shap
    total_prob = _sigmoid(total_log_odds)

    cat_shap: dict[str, float] = {}
    for feature, shap_val in shap_dict.items():
        if feature in excluded:
            continue

        if model_type == "pregame":
            cat = _classify_pregame(feature, suffix_rules, exact_map)
        else:
            cat = feat_to_cat.get(feature)

        if cat:
            cat_shap[cat] = cat_shap.get(cat, 0.0) + shap_val

    groups = []
    for category, group_shap in cat_shap.items():
        without = total_log_odds - group_shap
        prob_without = _sigmoid(without)
        impact_pct = round((total_prob - prob_without) * 100, 1)
        if abs(impact_pct) >= impact_threshold:
            groups.append({"category": category, "impactPct": impact_pct})

    groups.sort(key=lambda g: abs(g["impactPct"]), reverse=True)
    groups = groups[:max_groups]

    pregame_shap = shap_dict.get("pregame_blue_win_prob", 0)
    displayed_total = sum(abs(g["impactPct"]) for g in groups)

    if not groups and abs(pregame_shap) > 0.1:
        narrative = "Prediction largely driven by pregame draft and skill analysis."
    elif not groups:
        narrative = "An evenly matched game with no dominant factors."
    else:
        top = groups[0]
        direction = "Blue" if top["impactPct"] > 0 else "Red"
        magnitude = abs(top["impactPct"])
        if magnitude >= narr["strong_threshold"]:
            strength = "strong"
        elif magnitude >= narr["moderate_threshold"]:
            strength = "moderate"
        else:
            strength = "slight"
        narrative = f"{direction} favored by a {strength} {top['category'].lower()} edge"
        if len(groups) > 1 and abs(groups[1]["impactPct"]) >= narr["second_factor_threshold"]:
            second_dir = "blue" if groups[1]["impactPct"] > 0 else "red"
            verb = "supported" if second_dir == direction.lower() else "offset"
            narrative += f", {verb} by {groups[1]['category'].lower()}"
        if displayed_total < abs(pregame_shap) * narr["pregame_dominance_multiplier"]:
            narrative += " — largely driven by pregame analysis"
        narrative += "."

    return {"groups": groups, "narrative": narrative}


def _classify_pregame(
    name: str,
    suffix_rules: list[list] | None,
    exact_map: dict[str, str] | None,
) -> str | None:
    bare = re.sub(r"^(blue|red)_[a-z]{2,3}_", "", name)
    bare = re.sub(r"^(blue|red)_", "", bare)
    if exact_map and bare in exact_map:
        return exact_map[bare]
    if suffix_rules:
        for cat, suffixes in suffix_rules:
            for s in suffixes:
                if bare == s or bare.endswith(f"_{s}") or name.endswith(f"_{s}"):
                    return cat
    return None


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: shap_predict <model.json> [model_type]"}))
        sys.exit(1)

    model_path = sys.argv[1]
    model_type = sys.argv[2] if len(sys.argv) > 2 else "live"
    features = json.loads(sys.stdin.read())

    model = xgb.Booster()
    model.load_model(model_path)

    feature_names = list(features.keys())
    values = np.array([[features[f] for f in feature_names]], dtype=np.float32)
    df = pd.DataFrame(values, columns=feature_names)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(df)
    sv = shap_values[0] if len(shap_values.shape) > 1 else shap_values
    base = float(np.asarray(explainer.expected_value).flat[0])

    shap_dict = {name: round(float(val), 4) for name, val in zip(feature_names, sv)}

    result = {
        "base_value": round(base, 6),
        "shap_values": shap_dict,
    }

    config = _load_shap_config()
    if config:
        result["factor_analysis"] = _build_factor_analysis(base, shap_dict, model_type, config)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
