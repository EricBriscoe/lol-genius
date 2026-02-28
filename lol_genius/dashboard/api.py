from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

log = logging.getLogger(__name__)

router = APIRouter()

_training_lock = threading.Lock()
_training_status: dict | None = None
_sse_events: list[dict] = []


def _push_sse(event_type: str, data: dict):
    _sse_events.append({"event": event_type, "data": data, "ts": time.time()})
    if len(_sse_events) > 500:
        _sse_events[:] = _sse_events[-250:]


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
    db = request.app.state.db

    def _query():
        return {
            "match_count": db.get_match_count(),
            "queue_stats": db.get_queue_stats(),
            "enrichment": db.get_enrichment_stats(),
            "queue_depth": db.get_queue_depth(),
        }

    return await asyncio.to_thread(_query)


@router.get("/distributions")
async def distributions(request: Request):
    db = request.app.state.db

    def _query():
        rank_dist = db.get_rank_distribution()
        patch_dist = db.get_patch_distribution()
        tier_seed_stats = db.get_queue_stats_by_tier()
        age_range = db.get_match_age_range()

        match_age = None
        if age_range:
            oldest = datetime.fromtimestamp(age_range[0] / 1000, tz=timezone.utc).isoformat()
            newest = datetime.fromtimestamp(age_range[1] / 1000, tz=timezone.utc).isoformat()
            match_age = {"oldest": oldest, "newest": newest}

        return {
            "rank_distribution": rank_dist,
            "patch_distribution": patch_dist,
            "tier_seed_stats": tier_seed_stats,
            "match_age_range": match_age,
        }

    return await asyncio.to_thread(_query)


@router.get("/model/runs")
async def model_runs(request: Request):
    db = request.app.state.db

    def _query():
        runs = db.get_model_runs(limit=50)
        return [_serialize_model_run(dict(r)) for r in runs]

    return await asyncio.to_thread(_query)


@router.get("/model/runs/{run_id}")
async def model_run_detail(request: Request, run_id: str):
    db = request.app.state.db

    def _query():
        return db.get_model_run(run_id)

    run = await asyncio.to_thread(_query)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    return _serialize_model_run(run)


@router.post("/model/train")
async def trigger_training(request: Request):
    global _training_status

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
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    dsn = request.app.state.dsn
    model_dir = request.app.state.model_dir
    ddragon_cache = request.app.state.ddragon_cache

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_training_pipeline, dsn, model_dir, ddragon_cache, notes, run_id)

    return {"run_id": run_id, "status": "started"}


def _run_training_pipeline(dsn: str, model_dir: str, ddragon_cache: str, notes: str, run_id_hint: str):
    global _training_status

    if not _training_lock.acquire(blocking=False):
        return

    try:
        _training_status = {"stage": "building_features", "run_id": run_id_hint, "started_at": time.time()}
        _push_sse("training_status", {**_training_status})

        import pandas as pd

        from lol_genius.api.ddragon import DataDragon
        from lol_genius.db.queries import MatchDB
        from lol_genius.features.build import build_feature_matrix

        db = MatchDB(dsn)
        ddragon = DataDragon(ddragon_cache)

        try:
            X, y, patches, timestamps = build_feature_matrix(db, ddragon)
        finally:
            db.close()

        if X.empty:
            _training_status = {"stage": "error", "error": "No enriched matches found"}
            _push_sse("training_status", {**_training_status})
            return

        out_dir = Path(model_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        X.to_parquet(out_dir / "features.parquet")
        y.to_frame().to_parquet(out_dir / "targets.parquet")
        patches.to_frame().to_parquet(out_dir / "patches.parquet")
        timestamps.to_frame().to_parquet(out_dir / "timestamps.parquet")

        _training_status = {"stage": "training", "run_id": run_id_hint, "matches": len(X), "features": X.shape[1]}
        _push_sse("training_status", {**_training_status})

        from lol_genius.model.train import train_model

        model, actual_run_id = train_model(
            X, y, model_dir, patches=patches, timestamps=timestamps, database_url=dsn
        )

        if notes:
            db2 = MatchDB(dsn)
            try:
                db2.update_model_run(actual_run_id, {"notes": notes})
            finally:
                db2.close()

        _training_status = {"stage": "evaluating", "run_id": actual_run_id}
        _push_sse("training_status", {**_training_status})

        from lol_genius.model.evaluate import evaluate_model

        X_test = pd.read_parquet(out_dir / "X_test.parquet")
        y_test = pd.read_parquet(out_dir / "y_test.parquet").squeeze()
        metrics = evaluate_model(model, X_test, y_test, model_dir, database_url=dsn, run_id=actual_run_id)

        _training_status = {"stage": "explaining", "run_id": actual_run_id}
        _push_sse("training_status", {**_training_status})

        from lol_genius.model.explain import explain_model

        X_full = pd.read_parquet(out_dir / "features.parquet")
        feature_names_path = out_dir / "feature_names.json"
        if feature_names_path.exists():
            feat_names = json.loads(feature_names_path.read_text())
            X_full = X_full[[c for c in feat_names if c in X_full.columns]]

        explain_model(model, X_full, model_dir, database_url=dsn, run_id=actual_run_id)

        _training_status = {
            "stage": "completed",
            "run_id": actual_run_id,
            "metrics": metrics,
            "completed_at": time.time(),
        }
        _push_sse("training_status", {**_training_status})

    except Exception as e:
        log.exception("Training pipeline failed")
        _training_status = {"stage": "error", "error": str(e)}
        _push_sse("training_status", {**_training_status})
    finally:
        _training_lock.release()


@router.get("/system/health")
async def system_health(request: Request):
    db = request.app.state.db
    proxy_url = request.app.state.proxy_url

    def _db_check():
        try:
            db.get_match_count()
            return True
        except Exception as e:
            log.warning(f"DB health check failed: {e}")
            return False

    def _stale_check():
        try:
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
            return predict_live_game(proxy, db, ddragon, model_dir, game_data)
        finally:
            proxy.close()
            db.close()

    try:
        result = await asyncio.to_thread(_predict)
        return result
    except Exception as e:
        log.exception("Prediction failed")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/events")
async def sse_stream(request: Request):
    async def event_generator():
        last_idx = len(_sse_events)
        last_status_time = 0

        while True:
            if await request.is_disconnected():
                break

            now = time.time()
            if now - last_status_time >= 5:
                last_status_time = now
                try:
                    db = request.app.state.db

                    def _poll():
                        return {
                            "match_count": db.get_match_count(),
                            "queue_depth": db.get_queue_depth(),
                            "enrichment": db.get_enrichment_stats(),
                            "queue_stats": db.get_queue_stats(),
                        }

                    data = await asyncio.to_thread(_poll)
                    yield {"event": "crawler_status", "data": json.dumps(data)}
                except Exception as e:
                    log.warning(f"SSE crawler poll error: {e}")

            current_len = len(_sse_events)
            if current_len > last_idx:
                for evt in _sse_events[last_idx:current_len]:
                    yield {"event": evt["event"], "data": json.dumps(evt["data"])}
                last_idx = current_len

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())
