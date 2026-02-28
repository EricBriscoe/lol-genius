from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import shap
import xgboost as xgb

log = logging.getLogger(__name__)


def explain_model(
    model: xgb.Booster,
    X: pd.DataFrame,
    model_dir: str,
    max_samples: int = 5000,
    database_url: str | None = None,
    run_id: str | None = None,
) -> None:
    import matplotlib.pyplot as plt

    model_path = Path(model_dir)

    if len(X) > max_samples:
        X_sample = X.sample(n=max_samples, random_state=42)
    else:
        X_sample = X

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)

    fig = plt.figure(figsize=(12, 10))
    shap.summary_plot(shap_values, X_sample, show=False, max_display=30)
    plt.tight_layout()
    fig.savefig(model_path / "shap_summary.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info(f"SHAP summary plot saved to {model_path / 'shap_summary.png'}")

    fig = plt.figure(figsize=(12, 8))
    shap.summary_plot(shap_values, X_sample, plot_type="bar", show=False, max_display=30)
    plt.tight_layout()
    fig.savefig(model_path / "shap_importance.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info(f"SHAP importance plot saved to {model_path / 'shap_importance.png'}")

    mean_abs = np.abs(shap_values).mean(axis=0)
    top_indices = np.argsort(mean_abs)[-20:][::-1]
    top_features_list = [
        {"name": X_sample.columns[i], "importance": round(float(mean_abs[i]), 6)}
        for i in top_indices
    ]

    dep_indices = top_indices[:5]
    for i in dep_indices:
        feat = X_sample.columns[i]
        fig = plt.figure(figsize=(8, 6))
        shap.dependence_plot(feat, shap_values, X_sample, show=False)
        plt.tight_layout()
        safe_name = feat.replace("/", "_")
        fig.savefig(model_path / f"shap_dep_{safe_name}.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

    log.info(f"Top 5 features by SHAP importance: {[f['name'] for f in top_features_list[:5]]}")

    if database_url and run_id:
        import json
        from lol_genius.db.queries import MatchDB
        db = MatchDB(database_url)
        try:
            db.update_model_run(run_id, {
                "top_features": json.dumps(top_features_list),
            })
        finally:
            db.close()


def explain_single_match(
    model: xgb.Booster,
    match_features: pd.DataFrame,
    model_dir: str | None = None,
) -> dict:
    import matplotlib.pyplot as plt

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(match_features)

    dmatrix = xgb.DMatrix(match_features, feature_names=list(match_features.columns))
    prediction = model.predict(dmatrix)[0]

    log.info(f"\nPrediction: Blue win probability = {prediction:.2%}")
    log.info(f"{'Blue favored' if prediction > 0.5 else 'Red favored'}")

    sv = shap_values[0] if len(shap_values.shape) > 1 else shap_values
    feature_impacts = sorted(
        zip(match_features.columns, sv),
        key=lambda x: abs(x[1]),
        reverse=True,
    )

    log.info(f"\nTop 10 factors:")
    for name, impact in feature_impacts[:10]:
        direction = "→ Blue" if impact > 0 else "→ Red"
        log.info(f"  {name:40s} {impact:+.4f} {direction}")

    if model_dir:
        try:
            fig = plt.figure(figsize=(14, 6))
            shap.waterfall_plot(
                shap.Explanation(
                    values=sv,
                    base_values=explainer.expected_value,
                    data=match_features.iloc[0].values,
                    feature_names=list(match_features.columns),
                ),
                max_display=15,
                show=False,
            )
            plt.tight_layout()
            fig.savefig(Path(model_dir) / "single_match_explanation.png", dpi=150, bbox_inches="tight")
            plt.close(fig)
        except Exception as e:
            log.debug(f"Failed to save waterfall plot: {e}")

    return {
        "blue_win_probability": float(prediction),
        "top_factors": [(name, float(impact)) for name, impact in feature_impacts[:10]],
    }
