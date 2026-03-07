from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def export_onnx(model_dir: str, model_type: str = "pregame") -> Path:
    import onnxmltools
    import xgboost as xgb
    from onnxmltools.convert.common.data_types import FloatTensorType

    from lol_genius.model.train import load_model

    model, feature_names = load_model(model_dir, model_type)
    type_dir = Path(model_dir) / model_type

    sklearn_model = xgb.XGBClassifier()
    sklearn_model.load_model(str(type_dir / "model.json"))

    initial_type = [("input", FloatTensorType([None, len(feature_names)]))]
    onnx_model = onnxmltools.convert_xgboost(sklearn_model, initial_types=initial_type)

    out_path = type_dir / "model.onnx"
    with open(out_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    log.info("Exported ONNX model to %s", out_path)

    names_path = type_dir / "feature_names.json"
    names_path.write_text(json.dumps(feature_names, indent=2))

    _export_feature_importance(model, feature_names, type_dir)

    return out_path


def _export_feature_importance(
    model, feature_names: list[str], output_dir: Path
) -> Path:
    import pandas as pd
    import shap

    try:
        test_path = output_dir / "X_test.parquet"
        if test_path.exists():
            X_test = pd.read_parquet(test_path)
            X_sample = X_test.head(500)
        else:
            import numpy as np
            X_sample = pd.DataFrame(
                np.zeros((1, len(feature_names))), columns=feature_names
            )

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)
        mean_abs = pd.Series(
            data=abs(shap_values).mean(axis=0), index=feature_names
        ).sort_values(ascending=False)

        importance = [
            {"feature": name, "importance": round(float(val), 6)}
            for name, val in mean_abs.items()
        ]
    except Exception:
        log.warning("SHAP computation failed, using gain-based importance", exc_info=True)
        scores = model.get_score(importance_type="gain")
        total = sum(scores.values()) or 1.0
        importance = sorted(
            [
                {"feature": name, "importance": round(scores.get(name, 0.0) / total, 6)}
                for name in feature_names
            ],
            key=lambda x: x["importance"],
            reverse=True,
        )

    out_path = output_dir / "feature_importance.json"
    out_path.write_text(json.dumps(importance, indent=2))
    log.info("Exported feature importance to %s", out_path)
    return out_path
