from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split

if TYPE_CHECKING:
    import pandas as pd

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

LIVE_DEFAULT_PARAMS = {
    **DEFAULT_PARAMS,
    "max_depth": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.7,
    "min_child_weight": 5,
    "gamma": 0.2,
    "reg_lambda": 1.0,
}

PARAM_PRESETS = {
    "default": {**DEFAULT_PARAMS},
    "aggressive": {
        **DEFAULT_PARAMS,
        "max_depth": 6,
        "learning_rate": 0.08,
        "subsample": 0.8,
        "min_child_weight": 5,
        "gamma": 0.1,
    },
    "conservative": {
        **DEFAULT_PARAMS,
        "max_depth": 3,
        "learning_rate": 0.01,
        "subsample": 0.6,
        "min_child_weight": 15,
        "gamma": 0.5,
        "reg_lambda": 2.0,
    },
}

_TEST_SPLIT_RATIO = 0.2
_RANDOM_SEED = 42


def _compute_patch_weights(
    patches: pd.Series, decay_factor: float = 0.5
) -> np.ndarray:
    unique = sorted(
        patches.unique(), key=lambda p: [int(x) for x in p.split(".")] if p else [0]
    )
    if not unique:
        return np.ones(len(patches))

    patch_to_idx = {p: i for i, p in enumerate(unique)}
    latest_idx = len(unique) - 1
    weights = np.array(
        [decay_factor ** (latest_idx - patch_to_idx.get(p, 0)) for p in patches]
    )

    dist = {}
    for p in unique:
        mask = patches == p
        dist[p] = (
            int(mask.sum()),
            float(
                weights[mask].iloc[0]
                if hasattr(weights[mask], "iloc")
                else weights[mask.values][0]
            ),
        )
    log.info("Patch weight distribution:")
    for p, (count, w) in dist.items():
        log.info(f"  {p}: {count} matches, weight={w:.3f}")

    return weights


def select_features(
    X: pd.DataFrame,
    y: pd.Series,
    variance_threshold: float = 1e-6,
    correlation_threshold: float = 0.95,
) -> pd.DataFrame:
    import pandas as pd
    from sklearn.feature_selection import mutual_info_classif

    variances = X.var()
    X = X.loc[:, variances > variance_threshold]
    log.info(f"After variance filter: {X.shape[1]} features")

    corr = X.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    mi = mutual_info_classif(X.fillna(0), y, random_state=_RANDOM_SEED)
    mi_series = pd.Series(mi, index=X.columns)

    to_drop: set[str] = set()
    for col in upper.columns:
        correlated = upper.index[upper[col] > correlation_threshold].tolist()
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
    X: pd.DataFrame,
    y: pd.Series,
    model_dir: str,
    num_boost_round: int = 1000,
    patches: pd.Series | None = None,
    patch_decay: float = 0.85,
    timestamps: pd.Series | None = None,
    match_ids: pd.Series | None = None,
    game_creations: pd.Series | None = None,
    database_url: str | None = None,
    params: dict | None = None,
    model_type: str = "pregame",
    early_stopping_rounds: int = 75,
) -> tuple[xgb.Booster, str]:

    base = LIVE_DEFAULT_PARAMS if model_type == "live" else DEFAULT_PARAMS
    resolved_params = {**base, **(params or {})}

    run_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    model_path = Path(model_dir) / model_type
    model_path.mkdir(parents=True, exist_ok=True)

    if model_type != "live":
        X = select_features(X, y)
    else:
        log.info(
            "Skipping feature selection for live model (hand-curated sparse features)"
        )

    sample_weights = None
    if patches is not None and len(patches) > 0 and patches.nunique() > 1:
        sample_weights = _compute_patch_weights(patches, patch_decay)

    if match_ids is not None and len(match_ids) > 0 and game_creations is not None:
        import pandas as _pd

        unique_matches = (
            _pd.DataFrame(
                {"match_id": match_ids.values, "game_creation": game_creations.values}
            )
            .drop_duplicates("match_id")
            .sort_values("game_creation")
        )
        n_test_matches = max(1, int(len(unique_matches) * _TEST_SPLIT_RATIO))
        test_match_set = set(unique_matches["match_id"].iloc[-n_test_matches:])
        test_mask = match_ids.isin(test_match_set).values
        train_mask = ~test_mask
        X_train, X_test = X.loc[train_mask], X.loc[test_mask]
        y_train, y_test = y.loc[train_mask], y.loc[test_mask]
        w_train = sample_weights[train_mask] if sample_weights is not None else None
        log.info(
            "Using match-aware group split: %d train / %d test matches (%d / %d rows)",
            len(unique_matches) - n_test_matches,
            n_test_matches,
            train_mask.sum(),
            test_mask.sum(),
        )
    elif timestamps is not None and len(timestamps) > 0:
        sort_idx = np.argsort(timestamps.values)
        n_test = int(len(X) * _TEST_SPLIT_RATIO)
        train_idx = sort_idx[:-n_test]
        test_idx = sort_idx[-n_test:]
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        w_train = sample_weights[train_idx] if sample_weights is not None else None
        log.info("Using temporal train/test split")
    elif sample_weights is not None:
        X_train, X_test, y_train, y_test, w_train, _ = train_test_split(
            X,
            y,
            sample_weights,
            test_size=_TEST_SPLIT_RATIO,
            stratify=y,
            random_state=_RANDOM_SEED,
        )
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=_TEST_SPLIT_RATIO, stratify=y, random_state=_RANDOM_SEED
        )
        w_train = None

    if match_ids is not None and len(match_ids) > 0:
        total_match_count = int(match_ids.nunique())
        train_match_count = int(match_ids.reindex(X_train.index).nunique())
        test_match_count = int(match_ids.reindex(X_test.index).nunique())
    else:
        total_match_count = len(X)
        train_match_count = len(X_train)
        test_match_count = len(X_test)

    dtrain = xgb.DMatrix(
        X_train, label=y_train, feature_names=list(X.columns), weight=w_train
    )
    dtest = xgb.DMatrix(X_test, label=y_test, feature_names=list(X.columns))

    t0 = time.monotonic()
    model = xgb.train(
        resolved_params,
        dtrain,
        num_boost_round=num_boost_round,
        evals=[(dtrain, "train"), (dtest, "eval")],
        early_stopping_rounds=early_stopping_rounds,
        verbose_eval=25,
    )
    training_seconds = round(time.monotonic() - t0, 1)

    model.save_model(str(model_path / "model.json"))
    invalidate_model_cache(model_dir, model_type)

    with open(model_path / "feature_names.json", "w") as f:
        json.dump(list(X.columns), f)

    X_test.to_parquet(model_path / "X_test.parquet")
    y_test.to_frame().to_parquet(model_path / "y_test.parquet")

    (model_path / "run_id.txt").write_text(run_id)

    log.info(f"Model saved to {model_path / 'model.json'}")
    log.info(
        f"Best iteration: {model.best_iteration}, Best score: {model.best_score:.4f}"
    )
    log.info(f"Run ID: {run_id}")

    if database_url:
        from lol_genius.db.queries import MatchDB

        patch_min = (
            str(patches.min()) if patches is not None and len(patches) > 0 else None
        )
        patch_max = (
            str(patches.max()) if patches is not None and len(patches) > 0 else None
        )
        db = MatchDB(database_url)
        try:
            db.insert_model_run(
                {
                    "run_id": run_id,
                    "model_type": model_type,
                    "total_matches": total_match_count,
                    "train_count": train_match_count,
                    "test_count": test_match_count,
                    "feature_count": X.shape[1],
                    "patch_min": patch_min,
                    "patch_max": patch_max,
                    "target_mean": float(y.mean()),
                    "hyperparameters": json.dumps(resolved_params),
                    "best_iteration": model.best_iteration,
                    "best_train_score": float(model.best_score),
                    "training_seconds": training_seconds,
                    "accuracy": None,
                    "auc_roc": None,
                    "log_loss": None,
                    "tn": None,
                    "fp": None,
                    "fn": None,
                    "tp": None,
                    "top_features": None,
                    "notes": None,
                }
            )
        finally:
            db.close()

    return model, run_id


_tune_X: np.ndarray | None = None
_tune_y: np.ndarray | None = None


def _init_tune_worker(X: np.ndarray, y: np.ndarray):
    import os

    os.nice(10)
    global _tune_X, _tune_y
    _tune_X = X
    _tune_y = y


def _cv_single_combo(params: dict) -> tuple[float, dict, int]:
    dtrain = xgb.DMatrix(_tune_X, label=_tune_y)
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
    best_round = int(cv_results["test-logloss-mean"].idxmin()) + 1
    return score, params, best_round


def tune_hyperparameters(
    X: pd.DataFrame,
    y: pd.Series,
) -> dict:
    import multiprocessing
    import os
    from concurrent.futures import ProcessPoolExecutor
    from itertools import product

    X_np = X.values
    y_np = y.values

    param_grid = {
        "max_depth": [4, 6, 8],
        "learning_rate": [0.01, 0.05, 0.1],
        "subsample": [0.7, 0.8, 0.9],
        "colsample_bytree": [0.6, 0.8, 1.0],
        "min_child_weight": [3, 5, 10],
    }

    keys = list(param_grid.keys())
    values = list(param_grid.values())

    total = 1
    for v in values:
        total *= len(v)

    n_cpu = os.cpu_count() or 1
    n_workers = min(n_cpu, 4)
    nthread = max(1, n_cpu // n_workers)
    log.info(
        f"Grid search: {total} combinations, {n_workers} workers × {nthread} threads (nice 10)"
    )

    base_params = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "gamma": 0.1,
        "tree_method": "hist",
        "nthread": nthread,
    }

    combos = []
    for combo in product(*values):
        combos.append({**base_params, **dict(zip(keys, combo))})

    best_score = float("inf")
    best_params = {}
    best_round = 300

    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=n_workers,
        mp_context=ctx,
        initializer=_init_tune_worker,
        initargs=(X_np, y_np),
    ) as pool:
        for score, params, num_round in pool.map(_cv_single_combo, combos):
            if score < best_score:
                best_score = score
                best_params = params.copy()
                best_round = num_round
                log.info(f"New best: {score:.4f} with {params}")

    best_params["best_num_round"] = best_round
    log.info(f"Best params: {best_params} (score: {best_score:.4f})")
    return best_params


_model_cache: dict[tuple[str, str], tuple[xgb.Booster, list[str]]] = {}


def load_model(
    model_dir: str, model_type: str = "pregame"
) -> tuple[xgb.Booster, list[str]]:
    cache_key = (model_dir, model_type)
    if cache_key not in _model_cache:
        model_path = Path(model_dir) / model_type
        if not (model_path / "model.json").exists():
            model_path = Path(model_dir)
        if not (model_path / "model.json").exists():
            raise FileNotFoundError(
                f"No {model_type} model found. Go to Model Training to train one first."
            )
        model = xgb.Booster()
        model.load_model(str(model_path / "model.json"))
        with open(model_path / "feature_names.json") as f:
            feature_names = json.load(f)
        _model_cache[cache_key] = (model, feature_names)
    return _model_cache[cache_key]


def load_calibrator(model_dir: str, model_type: str = "pregame") -> dict | None:
    path = Path(model_dir) / model_type / "calibrator.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        log.warning("Failed to load calibrator: %s", e)
        return None


def invalidate_model_cache(
    model_dir: str | None = None, model_type: str | None = None
) -> None:
    if model_dir and model_type:
        _model_cache.pop((model_dir, model_type), None)
    elif model_dir:
        for k in [k for k in _model_cache if k[0] == model_dir]:
            _model_cache.pop(k, None)
    else:
        _model_cache.clear()
