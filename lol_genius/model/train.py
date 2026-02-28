from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold, train_test_split

log = logging.getLogger(__name__)

DEFAULT_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "max_depth": 4,
    "learning_rate": 0.03,
    "subsample": 0.7,
    "colsample_bytree": 0.6,
    "min_child_weight": 10,
    "gamma": 0.3,
    "reg_alpha": 0.1,
    "reg_lambda": 1.5,
    "tree_method": "hist",
}


def _compute_patch_weights(
    patches: "pd.Series", decay_factor: float = 0.5
) -> np.ndarray:
    unique = sorted(patches.unique(), key=lambda p: [int(x) for x in p.split(".")] if p else [0])
    if not unique:
        return np.ones(len(patches))

    patch_to_idx = {p: i for i, p in enumerate(unique)}
    latest_idx = len(unique) - 1
    weights = np.array([
        decay_factor ** (latest_idx - patch_to_idx.get(p, 0))
        for p in patches
    ])

    dist = {}
    for p in unique:
        mask = patches == p
        dist[p] = (int(mask.sum()), float(weights[mask].iloc[0] if hasattr(weights[mask], 'iloc') else weights[mask.values][0]))
    log.info("Patch weight distribution:")
    for p, (count, w) in dist.items():
        log.info(f"  {p}: {count} matches, weight={w:.3f}")

    return weights


def select_features(
    X: "pd.DataFrame", y: "pd.Series",
) -> "pd.DataFrame":
    import pandas as pd
    from sklearn.feature_selection import mutual_info_classif

    variances = X.var()
    X = X.loc[:, variances > 1e-6]
    log.info(f"After variance filter: {X.shape[1]} features")

    corr = X.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    mi = mutual_info_classif(X.fillna(0), y, random_state=42)
    mi_series = pd.Series(mi, index=X.columns)

    to_drop: set[str] = set()
    for col in upper.columns:
        correlated = upper.index[upper[col] > 0.95].tolist()
        for corr_col in correlated:
            if mi_series.get(col, 0) >= mi_series.get(corr_col, 0):
                to_drop.add(corr_col)
            else:
                to_drop.add(col)
    X = X.drop(columns=[c for c in to_drop if c in X.columns])
    log.info(f"After correlation filter: {X.shape[1]} features")

    log.info(f"Final feature count: {X.shape[1]}")
    return X


def train_model(
    X: "pd.DataFrame",
    y: "pd.Series",
    model_dir: str,
    num_boost_round: int = 1000,
    patches: "pd.Series | None" = None,
    patch_decay: float = 0.85,
    timestamps: "pd.Series | None" = None,
    database_url: str | None = None,
) -> tuple[xgb.Booster, str]:
    import pandas as pd

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_path = Path(model_dir)
    model_path.mkdir(parents=True, exist_ok=True)

    X = select_features(X, y)

    sample_weights = None
    if patches is not None and len(patches) > 0 and patches.nunique() > 1:
        sample_weights = _compute_patch_weights(patches, patch_decay)

    if timestamps is not None and len(timestamps) > 0:
        sort_idx = np.argsort(timestamps.values)
        n_test = int(len(X) * 0.2)
        train_idx = sort_idx[:-n_test]
        test_idx = sort_idx[-n_test:]
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        w_train = sample_weights[train_idx] if sample_weights is not None else None
        log.info("Using temporal train/test split")
    elif sample_weights is not None:
        X_train, X_test, y_train, y_test, w_train, _ = train_test_split(
            X, y, sample_weights, test_size=0.2, stratify=y, random_state=42
        )
    else:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
        w_train = None

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=list(X.columns), weight=w_train)
    dtest = xgb.DMatrix(X_test, label=y_test, feature_names=list(X.columns))

    t0 = time.monotonic()
    model = xgb.train(
        DEFAULT_PARAMS,
        dtrain,
        num_boost_round=num_boost_round,
        evals=[(dtrain, "train"), (dtest, "eval")],
        early_stopping_rounds=75,
        verbose_eval=25,
    )
    training_seconds = round(time.monotonic() - t0, 1)

    model.save_model(str(model_path / "model.json"))

    with open(model_path / "feature_names.json", "w") as f:
        json.dump(list(X.columns), f)

    X_test.to_parquet(model_path / "X_test.parquet")
    y_test.to_frame().to_parquet(model_path / "y_test.parquet")

    (model_path / "run_id.txt").write_text(run_id)

    log.info(f"Model saved to {model_path / 'model.json'}")
    log.info(f"Best iteration: {model.best_iteration}, Best score: {model.best_score:.4f}")
    log.info(f"Run ID: {run_id}")

    if database_url:
        from lol_genius.db.queries import MatchDB
        patch_min = str(patches.min()) if patches is not None and len(patches) > 0 else None
        patch_max = str(patches.max()) if patches is not None and len(patches) > 0 else None
        db = MatchDB(database_url)
        try:
            db.insert_model_run({
                "run_id": run_id,
                "total_matches": len(X),
                "train_count": len(X_train),
                "test_count": len(X_test),
                "feature_count": X.shape[1],
                "patch_min": patch_min,
                "patch_max": patch_max,
                "target_mean": float(y.mean()),
                "hyperparameters": json.dumps(DEFAULT_PARAMS),
                "best_iteration": model.best_iteration,
                "best_train_score": float(model.best_score),
                "training_seconds": training_seconds,
                "accuracy": None, "auc_roc": None, "log_loss": None,
                "tn": None, "fp": None, "fn": None, "tp": None,
                "top_features": None, "notes": None,
            })
        finally:
            db.close()

    return model, run_id


def tune_hyperparameters(
    X: "pd.DataFrame",
    y: "pd.Series",
) -> dict:
    import pandas as pd

    param_grid = {
        "max_depth": [4, 6, 8],
        "learning_rate": [0.01, 0.05, 0.1],
        "subsample": [0.7, 0.8, 0.9],
        "colsample_bytree": [0.6, 0.8, 1.0],
        "min_child_weight": [3, 5, 10],
    }

    best_score = float("inf")
    best_params = {}

    from itertools import product

    keys = list(param_grid.keys())
    values = list(param_grid.values())

    dtrain = xgb.DMatrix(X, label=y, feature_names=list(X.columns))

    total = 1
    for v in values:
        total *= len(v)
    log.info(f"Grid search: {total} combinations")

    for combo in product(*values):
        params = dict(zip(keys, combo))
        params.update({
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "gamma": 0.1,
            "tree_method": "hist",
        })

        cv_results = xgb.cv(
            params,
            dtrain,
            num_boost_round=300,
            nfold=5,
            early_stopping_rounds=30,
            verbose_eval=False,
            stratified=True,
        )

        score = cv_results["test-logloss-mean"].min()
        if score < best_score:
            best_score = score
            best_params = params.copy()
            best_params["best_num_round"] = cv_results["test-logloss-mean"].idxmin() + 1
            log.info(f"New best: {score:.4f} with {params}")

    log.info(f"Best params: {best_params} (score: {best_score:.4f})")
    return best_params


def load_model(model_dir: str) -> tuple[xgb.Booster, list[str]]:
    model_path = Path(model_dir)
    model = xgb.Booster()
    model.load_model(str(model_path / "model.json"))

    with open(model_path / "feature_names.json") as f:
        feature_names = json.load(f)

    return model, feature_names
