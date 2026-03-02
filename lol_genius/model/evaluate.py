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

    log.info(
        f"\nClassification Report:\n{classification_report(y_test, y_pred, target_names=['Red Win', 'Blue Win'])}"
    )

    if model_dir:
        _plot_calibration(y_test, y_proba, model_dir)

    if database_url and run_id:
        from lol_genius.db.queries import MatchDB

        db = MatchDB(database_url)
        try:
            db.update_model_run(
                run_id,
                {
                    "accuracy": float(metrics["accuracy"]),
                    "auc_roc": float(metrics["auc_roc"]),
                    "log_loss": float(metrics["log_loss"]),
                    "tn": int(cm[0][0]),
                    "fp": int(cm[0][1]),
                    "fn": int(cm[1][0]),
                    "tp": int(cm[1][1]),
                },
            )
        finally:
            db.close()

    return metrics


def _plot_calibration(y_test: pd.Series, y_proba: np.ndarray, model_dir: str) -> None:
    try:
        import matplotlib.pyplot as plt

        prob_true, prob_pred = calibration_curve(y_test, y_proba, n_bins=10)

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(prob_pred, prob_true, marker="o", label="Model")
        ax.plot(
            [0, 1], [0, 1], linestyle="--", color="gray", label="Perfectly calibrated"
        )
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
