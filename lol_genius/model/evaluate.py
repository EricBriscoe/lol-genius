from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    log_loss,
    roc_auc_score,
)

log = logging.getLogger(__name__)


def evaluate_model(
    model: xgb.Booster,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    model_dir: str | None = None,
    database_url: str | None = None,
    run_id: str | None = None,
) -> dict:
    dtest = xgb.DMatrix(X_test, feature_names=list(X_test.columns))
    y_proba = model.predict(dtest)
    y_pred = (y_proba >= 0.5).astype(int)

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "auc_roc": roc_auc_score(y_test, y_proba),
        "log_loss": log_loss(y_test, y_proba),
    }

    log.info(f"\n{'=' * 50}")
    log.info("Model Evaluation Results")
    log.info(f"{'=' * 50}")
    log.info(f"Accuracy:  {metrics['accuracy']:.4f}")
    log.info(f"AUC-ROC:   {metrics['auc_roc']:.4f}")
    log.info(f"Log Loss:  {metrics['log_loss']:.4f}")

    cm = confusion_matrix(y_test, y_pred)
    log.info("\nConfusion Matrix:")
    log.info(f"  TN={cm[0][0]:5d}  FP={cm[0][1]:5d}")
    log.info(f"  FN={cm[1][0]:5d}  TP={cm[1][1]:5d}")

    report = classification_report(y_test, y_pred, target_names=["Red Win", "Blue Win"])
    log.info(f"\nClassification Report:\n{report}")

    if model_dir:
        _plot_calibration(y_test, y_proba, model_dir)
        _save_calibrator(y_test, y_proba, model_dir)

    time_window_metrics = _compute_time_window_metrics(X_test, y_test, y_proba)
    if time_window_metrics is not None:
        metrics["time_window_metrics"] = time_window_metrics

    if database_url and run_id:
        from lol_genius.db.queries import MatchDB

        db = MatchDB(database_url)
        try:
            update_payload: dict = {
                "accuracy": float(metrics["accuracy"]),
                "auc_roc": float(metrics["auc_roc"]),
                "log_loss": float(metrics["log_loss"]),
                "tn": int(cm[0][0]),
                "fp": int(cm[0][1]),
                "fn": int(cm[1][0]),
                "tp": int(cm[1][1]),
            }
            if time_window_metrics is not None:
                update_payload["time_window_metrics"] = time_window_metrics
            db.update_model_run(run_id, update_payload)
        finally:
            db.close()

    return metrics


def _compute_time_window_metrics(
    X_test: pd.DataFrame, y_test: pd.Series, y_proba: np.ndarray
) -> list[dict] | None:
    if "game_time_seconds" not in X_test.columns:
        return None

    df = X_test[["game_time_seconds"]].copy()
    df["y_true"] = y_test.values
    df["y_proba"] = y_proba

    results = []
    for snapshot_seconds, group in df.groupby("game_time_seconds"):
        if len(group) < 30:
            continue
        minutes = int(snapshot_seconds // 60)
        accuracy = float(((group["y_proba"] >= 0.5).astype(int) == group["y_true"]).mean())
        auc = None
        if group["y_true"].nunique() > 1:
            try:
                auc = float(roc_auc_score(group["y_true"], group["y_proba"]))
            except Exception:
                log.warning("roc_auc_score failed for window %dm", minutes)
        results.append(
            {
                "minutes": minutes,
                "accuracy": accuracy,
                "auc_roc": auc,
                "count": len(group),
            }
        )

    return sorted(results, key=lambda x: x["minutes"]) if results else None


def _save_calibrator(y_test: pd.Series, y_proba: np.ndarray, model_dir: str) -> None:
    import json

    try:
        from sklearn.isotonic import IsotonicRegression

        cal = IsotonicRegression(out_of_bounds="clip").fit(y_proba, y_test)
        calibrator_data = {
            "x_thresholds": cal.X_thresholds_.tolist(),
            "y_thresholds": cal.y_thresholds_.tolist(),
        }
        path = Path(model_dir) / "calibrator.json"
        path.write_text(json.dumps(calibrator_data))
        log.info(f"Calibrator saved to {path}")
    except Exception as e:
        log.warning(f"Failed to save calibrator: {e}")


def _plot_calibration(y_test: pd.Series, y_proba: np.ndarray, model_dir: str) -> None:
    try:
        import matplotlib.pyplot as plt

        prob_true, prob_pred = calibration_curve(y_test, y_proba, n_bins=10)

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(prob_pred, prob_true, marker="o", label="Model")
        ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfectly calibrated")
        ax.set_xlabel("Mean predicted probability")
        ax.set_ylabel("Fraction of positives")
        ax.set_title("Calibration Curve")
        ax.legend()

        path = Path(model_dir) / "calibration.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        log.info(f"Calibration plot saved to {path}")
    except Exception as e:
        log.warning(f"Failed to plot calibration: {e}")
