"""Standalone SHAP prediction sidecar.

Reads a model path from argv[1] and feature JSON from stdin.
Outputs per-feature SHAP values as JSON to stdout.
"""

import json
import sys

import numpy as np
import pandas as pd
import shap
import xgboost as xgb


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: shap_predict <model.json>"}))
        sys.exit(1)

    model_path = sys.argv[1]
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

    result = {
        "base_value": round(base, 6),
        "shap_values": {name: round(float(val), 4) for name, val in zip(feature_names, sv)},
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
