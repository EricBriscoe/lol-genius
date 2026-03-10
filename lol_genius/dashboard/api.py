from __future__ import annotations

import asyncio
import itertools
import json
import logging
import threading
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from lol_genius.db.queries import pooled_db

log = logging.getLogger(__name__)

router = APIRouter()

_training_lock = threading.Lock()
_poller_lock = threading.Lock()
_training_status: dict | None = None
_sse_events: deque[dict] = deque(maxlen=500)
_sse_counter = itertools.count(1)
_live_game_poller = None


def _push_sse(event_type: str, data: dict):
    _sse_events.append(
        {
            "id": next(_sse_counter),
            "event": event_type,
            "data": data,
        }
    )


def _set_stage(stage_dict: dict):
    global _training_status
    _training_status = stage_dict
    _push_sse("training_status", {**stage_dict})


def _serialize_model_run(run: dict) -> dict:
    for key in ("hyperparameters", "top_features"):
        if run.get(key) and isinstance(run[key], str):
            try:
                run[key] = json.loads(run[key])
            except (json.JSONDecodeError, TypeError):
                pass
    if run.get("created_at") and hasattr(run["created_at"], "isoformat"):
        run["created_at"] = run["created_at"].isoformat()
    return run


@router.get("/status")
async def status(request: Request):
    pool = request.app.state.pool

    def _query():
        with pooled_db(pool) as db:
            return {
                "match_count": db.get_match_count(),
                "queue_stats": db.get_queue_stats(),
                "enrichment": db.get_enrichment_stats(),
                "timeline": db.get_timeline_stats(),
                "queue_depth": db.get_queue_depth(),
            }

    return await asyncio.to_thread(_query)


@router.get("/distributions")
async def distributions(request: Request):
    pool = request.app.state.pool

    def _query():
        with pooled_db(pool) as db:
            rank_dist = db.get_rank_distribution()
            patch_dist = db.get_patch_distribution()
            tier_seed_stats = db.get_queue_stats_by_tier()
            age_range = db.get_match_age_range()
            crawl_rate_raw = db.get_crawl_rate_history()

        match_age = None
        if age_range:
            oldest = datetime.fromtimestamp(age_range[0] / 1000, tz=UTC).isoformat()
            newest = datetime.fromtimestamp(age_range[1] / 1000, tz=UTC).isoformat()
            match_age = {"oldest": oldest, "newest": newest}

        crawl_rate = [
            {"hour": r["hour"].replace(tzinfo=UTC).isoformat(), "count": r["count"]}
            for r in crawl_rate_raw
        ]

        return {
            "rank_distribution": rank_dist,
            "patch_distribution": patch_dist,
            "tier_seed_stats": tier_seed_stats,
            "match_age_range": match_age,
            "crawl_rate": crawl_rate,
        }

    return await asyncio.to_thread(_query)


_VALID_MODEL_TYPES = {"pregame", "live"}


@router.get("/model/runs")
async def model_runs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    model_type: str | None = Query(default=None),
):
    if model_type is not None and model_type not in _VALID_MODEL_TYPES:
        return JSONResponse({"error": "Invalid model_type"}, status_code=400)
    pool = request.app.state.pool

    def _query():
        with pooled_db(pool) as db:
            runs = db.get_model_runs(limit=limit, model_type=model_type)
            return [_serialize_model_run(dict(r)) for r in runs]

    return await asyncio.to_thread(_query)


@router.get("/model/runs/{run_id}")
async def model_run_detail(request: Request, run_id: str):
    pool = request.app.state.pool

    def _query():
        with pooled_db(pool) as db:
            return db.get_model_run(run_id)

    run = await asyncio.to_thread(_query)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    return _serialize_model_run(run)


@router.get("/model/presets")
async def model_presets():
    from lol_genius.model.train import PARAM_PRESETS

    return PARAM_PRESETS


@router.get("/model/training-status")
async def training_status():
    return _training_status or {"stage": "idle"}


@router.post("/model/train")
async def trigger_training(request: Request):
    if _training_lock.locked():
        return JSONResponse(
            {"error": "Training already in progress", "status": _training_status},
            status_code=409,
        )

    body = {}
    try:
        body = await request.json()
    except (ValueError, TypeError):
        pass

    notes = body.get("notes", "")
    preset = body.get("preset")
    custom_params = body.get("params")
    auto_tune = body.get("auto_tune", False)
    model_type = body.get("model_type", "pregame")

    if model_type not in _VALID_MODEL_TYPES:
        return JSONResponse({"error": "Invalid model_type"}, status_code=400)
    run_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    from lol_genius.model.train import DEFAULT_PARAMS, PARAM_PRESETS

    resolved_params = None
    if auto_tune:
        resolved_params = "__auto_tune__"
    elif custom_params and isinstance(custom_params, dict):
        resolved_params = {**DEFAULT_PARAMS, **custom_params}
    elif preset and preset in PARAM_PRESETS:
        resolved_params = PARAM_PRESETS[preset]

    dsn = request.app.state.dsn
    model_dir = request.app.state.model_dir
    ddragon_cache = request.app.state.ddragon_cache

    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None,
        _run_training_pipeline,
        dsn,
        model_dir,
        ddragon_cache,
        notes,
        run_id,
        resolved_params,
        model_type,
    )

    return {"run_id": run_id, "status": "started"}


def _run_training_pipeline(
    dsn: str,
    model_dir: str,
    ddragon_cache: str,
    notes: str,
    run_id_hint: str,
    resolved_params=None,
    model_type: str = "pregame",
):
    global _training_status

    if not _training_lock.acquire(blocking=False):
        return

    try:
        _set_stage(
            {
                "stage": "building_features",
                "run_id": run_id_hint,
                "started_at": time.time(),
            }
        )

        import pandas as pd

        from lol_genius.db.queries import MatchDB
        from lol_genius.model.train import train_model

        type_dir = Path(model_dir) / model_type
        type_dir.mkdir(parents=True, exist_ok=True)

        if model_type == "live":
            db = MatchDB(dsn)
            try:
                from lol_genius.api.ddragon import DataDragon
                from lol_genius.features.timeline import build_timeline_feature_matrix

                X, y, match_ids, game_creations = build_timeline_feature_matrix(
                    db, model_type="live", ddragon=DataDragon(ddragon_cache)
                )
            finally:
                db.close()
            patches = None
            timestamps = None
        else:
            from lol_genius.api.ddragon import DataDragon
            from lol_genius.features.build import build_feature_matrix

            db = MatchDB(dsn)
            ddragon = DataDragon(ddragon_cache)
            try:
                X, y, patches, timestamps, match_ids = build_feature_matrix(db, ddragon)
            finally:
                db.close()

            out_dir = Path(model_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            X.to_parquet(out_dir / "features.parquet")
            y.to_frame().to_parquet(out_dir / "targets.parquet")
            patches.to_frame().to_parquet(out_dir / "patches.parquet")
            timestamps.to_frame().to_parquet(out_dir / "timestamps.parquet")
            match_ids.to_frame().to_parquet(out_dir / "match_ids.parquet")
            game_creations = None

        if X.empty:
            _set_stage({"stage": "error", "error": "No training data found"})
            return

        match_count = (
            match_ids.nunique() if match_ids is not None and len(match_ids) > 0 else len(X)
        )

        train_params = None
        tuned_num_round = 1000
        if resolved_params == "__auto_tune__":
            _set_stage(
                {
                    "stage": "tuning",
                    "run_id": run_id_hint,
                    "matches": match_count,
                    "features": X.shape[1],
                }
            )

            from lol_genius.model.train import tune_hyperparameters

            tuned = tune_hyperparameters(X, y)
            tuned_num_round = tuned.pop("best_num_round", 1000)
            train_params = tuned
        elif isinstance(resolved_params, dict):
            train_params = resolved_params

        _set_stage(
            {
                "stage": "training",
                "run_id": run_id_hint,
                "matches": match_count,
                "features": X.shape[1],
            }
        )

        train_kwargs = dict(
            patches=patches,
            timestamps=timestamps,
            database_url=dsn,
            params=train_params,
            model_type=model_type,
        )
        if model_type == "live":
            train_kwargs["match_ids"] = match_ids
            train_kwargs["game_creations"] = game_creations
        if resolved_params == "__auto_tune__":
            train_kwargs["num_boost_round"] = tuned_num_round

        model, actual_run_id = train_model(X, y, model_dir, **train_kwargs)

        if model_type == "pregame" and match_ids is not None and not match_ids.empty:
            import xgboost as xgb

            from lol_genius.model.train import load_model as _load_model

            try:
                m, feat_names = _load_model(model_dir, "pregame")
                feat_df = X[[c for c in feat_names if c in X.columns]]
                dmat = xgb.DMatrix(feat_df, feature_names=feat_names)
                probs = m.predict(dmat)
                pairs = list(zip(match_ids.tolist(), probs.tolist()))
                db3 = MatchDB(dsn)
                try:
                    db3.bulk_update_pregame_probs(pairs)
                    log.info("Stored pregame probs for %d matches", len(pairs))
                finally:
                    db3.close()
            except Exception as e:
                log.warning("Could not store pregame probs: %s", e)

        if notes:
            db2 = MatchDB(dsn)
            try:
                db2.update_model_run(actual_run_id, {"notes": notes})
            finally:
                db2.close()

        _set_stage({"stage": "evaluating", "run_id": actual_run_id})

        from lol_genius.model.evaluate import evaluate_model

        X_test = pd.read_parquet(type_dir / "X_test.parquet")
        y_test = pd.read_parquet(type_dir / "y_test.parquet").squeeze()
        metrics = evaluate_model(
            model, X_test, y_test, str(type_dir), database_url=dsn, run_id=actual_run_id
        )

        _set_stage({"stage": "explaining", "run_id": actual_run_id})

        from lol_genius.model.explain import explain_model

        feature_names_path = type_dir / "feature_names.json"
        if feature_names_path.exists():
            feat_names = json.loads(feature_names_path.read_text())
            X_shap = X[[c for c in feat_names if c in X.columns]]
        else:
            X_shap = X

        explain_model(model, X_shap, str(type_dir), database_url=dsn, run_id=actual_run_id)

        _set_stage(
            {
                "stage": "completed",
                "run_id": actual_run_id,
                "metrics": metrics,
                "completed_at": time.time(),
            }
        )

    except Exception as e:
        log.exception("Training pipeline failed")
        _set_stage({"stage": "error", "error": str(e)})
    finally:
        _training_lock.release()


@router.get("/system/health")
async def system_health(request: Request):
    pool = request.app.state.pool
    proxy_url = request.app.state.proxy_url

    def _db_check():
        try:
            with pooled_db(pool) as db:
                db.get_match_count()
            return True
        except Exception as e:
            log.warning(f"DB health check failed: {e}")
            return False

    def _stale_check():
        try:
            with pooled_db(pool) as db:
                return db.get_stale_enrichment_counts()
        except Exception as e:
            log.warning(f"Stale enrichment check failed: {e}")
            return {}

    db_ok = await asyncio.to_thread(_db_check)

    proxy_health = None
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{proxy_url}/riot/v1/health")
            if resp.status_code == 200:
                proxy_health = resp.json()
    except Exception as e:
        log.warning(f"Proxy health check failed: {e}")

    stale = await asyncio.to_thread(_stale_check)

    return {
        "db_ok": db_ok,
        "proxy_health": proxy_health,
        "stale_enrichment": stale,
    }


@router.get("/champions/stats")
async def champion_stats(
    request: Request,
    patch: str | None = Query(default=None),
    tier: str | None = Query(default=None),
):
    from lol_genius.db.queries import TIER_ORDER

    if tier is not None and tier not in TIER_ORDER:
        return JSONResponse({"error": f"Invalid tier: {tier}"}, status_code=400)

    pool = request.app.state.pool
    ddragon_cache = request.app.state.ddragon_cache

    def _query():
        from lol_genius.api.ddragon import DataDragon

        with pooled_db(pool) as db:
            patch_dist = db.get_patch_distribution()
            resolved_patch = patch
            if not resolved_patch and patch_dist:
                resolved_patch = max(
                    patch_dist,
                    key=lambda p: (
                        int(p.split(".")[0]) if "." in p else 0,
                        int(p.split(".")[1]) if "." in p else 0,
                    ),
                )
            stats = db.get_champion_stats(resolved_patch, tier=tier)
            ban_stats = db.get_champion_ban_stats(resolved_patch, tier=tier)
            if tier:
                total_matches = db.get_tier_match_count(resolved_patch, tier)
            else:
                total_matches = (
                    patch_dist.get(resolved_patch, 0)
                    if resolved_patch
                    else sum(patch_dist.values())
                )

        ddragon = DataDragon(ddragon_cache)
        champ_data = ddragon.fetch_champion_data()
        champ_info = {}
        if champ_data:
            for c in champ_data.values():
                cid = int(c.get("key", 0))
                champ_info[cid] = {
                    "tags": c.get("tags", []),
                    "attack_range": c.get("stats", {}).get("attackrange", 0),
                }

        champions = []
        for s in stats:
            cid = s["champion_id"]
            info = champ_info.get(cid, {})
            bans = ban_stats.get(cid, 0)
            champions.append(
                {
                    **s,
                    "winrate": round(s["wins"] / s["games"], 4) if s["games"] else 0,
                    "pick_rate": round(s["games"] / total_matches, 4) if total_matches else 0,
                    "ban_rate": round(bans / total_matches, 4) if total_matches else 0,
                    "bans": bans,
                    "tags": info.get("tags", []),
                    "attack_range": info.get("attack_range", 0),
                }
            )

        return {
            "total_matches": total_matches,
            "patch": resolved_patch,
            "available_patches": list(patch_dist.keys()),
            "tier": tier,
            "available_tiers": list(TIER_ORDER.keys()),
            "champions": champions,
        }

    return await asyncio.to_thread(_query)


@router.get("/predict/lookup")
async def predict_lookup(request: Request, game_name: str = Query(...), tag_line: str = Query(...)):
    proxy_url = request.app.state.proxy_url

    def _lookup():
        from lol_genius.api.proxy_client import ProxyClient

        proxy = ProxyClient(proxy_url)
        try:
            account = proxy.get_account_by_riot_id(game_name, tag_line)
            if not account:
                return {"found": False, "error": "Player not found"}

            puuid = account.get("puuid")
            if not puuid:
                return {"found": False, "error": "Could not resolve PUUID"}

            active_game = proxy.get_active_game(puuid)
            return {
                "found": True,
                "puuid": puuid,
                "game_name": account.get("gameName", game_name),
                "tag_line": account.get("tagLine", tag_line),
                "in_game": active_game is not None,
                "game_data": active_game,
            }
        finally:
            proxy.close()

    return await asyncio.to_thread(_lookup)


@router.post("/predict/live")
async def predict_live(request: Request):
    body = await request.json()
    game_data = body.get("game_data")
    if not game_data:
        return JSONResponse({"error": "game_data required"}, status_code=400)

    proxy_url = request.app.state.proxy_url
    dsn = request.app.state.dsn
    model_dir = request.app.state.model_dir
    ddragon_cache = request.app.state.ddragon_cache

    def _predict():
        from lol_genius.api.ddragon import DataDragon
        from lol_genius.api.proxy_client import ProxyClient
        from lol_genius.db.queries import MatchDB
        from lol_genius.predict.live import predict_live_game

        proxy = ProxyClient(proxy_url)
        db = MatchDB(dsn)
        ddragon = DataDragon(ddragon_cache)
        try:
            return predict_live_game(proxy, db, ddragon, model_dir, game_data, dsn=dsn)
        finally:
            proxy.close()
            db.close()

    try:
        result = await asyncio.to_thread(_predict)
        return result
    except FileNotFoundError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception:
        log.exception("Prediction failed")
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.post("/live-game/start")
async def live_game_start(request: Request):
    global _live_game_poller

    body = {}
    try:
        body = await request.json()
    except (ValueError, TypeError):
        pass

    host = body.get("host", "localhost")
    try:
        port = int(body.get("port", 2999))
    except (ValueError, TypeError):
        return JSONResponse({"error": "port must be an integer"}, status_code=400)
    if not (1024 <= port <= 65535):
        return JSONResponse({"error": "port must be between 1024 and 65535"}, status_code=400)
    pregame_win_prob = body.get("pregame_win_prob")
    if pregame_win_prob is not None:
        pregame_win_prob = float(pregame_win_prob)
    model_dir = request.app.state.model_dir
    dsn = request.app.state.dsn
    proxy_url = request.app.state.proxy_url
    ddragon_cache = request.app.state.ddragon_cache

    from lol_genius.predict.live_client import LiveGamePoller

    with _poller_lock:
        if _live_game_poller is not None:
            _live_game_poller.stop()
        _live_game_poller = LiveGamePoller(
            host,
            port,
            model_dir,
            _push_sse,
            pregame_win_prob=pregame_win_prob,
            dsn=dsn,
            proxy_url=proxy_url,
            ddragon_cache=ddragon_cache,
        )
        _live_game_poller.start()
    return {"status": "started", "host": host, "port": port}


@router.delete("/live-game/stop")
async def live_game_stop():
    global _live_game_poller
    with _poller_lock:
        if _live_game_poller is not None:
            _live_game_poller.stop()
            _live_game_poller = None
    return {"status": "stopped"}


@router.get("/live-game/status")
async def live_game_status():
    with _poller_lock:
        poller = _live_game_poller
    if poller is None:
        return {
            "connected": False,
            "host": None,
            "port": None,
            "current": None,
            "history": [],
        }
    snap = poller.snapshot()
    return {
        "connected": True,
        "host": poller.host,
        "port": poller.port,
        **snap,
    }


@router.get("/events")
async def sse_stream(request: Request):
    pool = request.app.state.pool

    def _poll():
        with pooled_db(pool) as db:
            return {
                "match_count": db.get_match_count(),
                "queue_depth": db.get_queue_depth(),
                "enrichment": db.get_enrichment_stats(),
                "timeline": db.get_timeline_stats(),
                "queue_stats": db.get_queue_stats(),
            }

    async def event_generator():
        last_seen_id = _sse_events[-1]["id"] if _sse_events else 0
        last_status_time = 0

        while True:
            if await request.is_disconnected():
                break

            now = time.time()
            if now - last_status_time >= 5:
                last_status_time = now
                try:
                    data = await asyncio.to_thread(_poll)
                    yield {"event": "crawler_status", "data": json.dumps(data)}
                except Exception as e:
                    log.warning(f"SSE crawler poll error: {e}")

            new_events = [e for e in _sse_events if e["id"] > last_seen_id]
            for evt in new_events:
                yield {"event": evt["event"], "data": json.dumps(evt["data"])}
                last_seen_id = evt["id"]

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())
