from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from lol_genius.api.client import APIKeyExpiredError, BadRequestError
from lol_genius.proxy.cache import ProxyCache
from lol_genius.proxy.key_pool import KeyPool

log = logging.getLogger(__name__)

CACHE_TTLS = {
    "summoner": 3600,
    "league_entries": 300,
    "league_by_puuid": 3600,
    "league_by_summoner": 3600,
    "match_ids": 600,
    "match": 604800,
    "mastery": 3600,
    "account": 3600,
    "spectator": 30,
}


def _load_api_keys() -> list[str]:
    csv_keys = os.environ.get("RIOT_API_KEYS", "")
    if csv_keys:
        keys = [k.strip() for k in csv_keys.split(",") if k.strip()]
        if keys:
            return keys

    numbered = []
    for i in range(1, 20):
        k = os.environ.get(f"RIOT_API_KEY_{i}", "")
        if k:
            numbered.append(k)
    if numbered:
        return numbered

    single = os.environ.get("RIOT_API_KEY", "")
    if single:
        return [single]

    raise RuntimeError("No API keys found. Set RIOT_API_KEYS, RIOT_API_KEY_N, or RIOT_API_KEY.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    keys = _load_api_keys()
    region = os.environ.get("LOL_GENIUS_REGION", "na1")
    routing = os.environ.get("LOL_GENIUS_ROUTING", "americas")
    rate_scale = float(os.environ.get("LOL_GENIUS_RATE_SCALE", "1.0"))

    pool = KeyPool(keys, rate_scale=rate_scale)
    cache = ProxyCache()

    app.state.pool = pool
    app.state.cache = cache
    app.state.region_url = f"https://{region}.api.riotgames.com"
    app.state.routing_url = f"https://{routing}.api.riotgames.com"

    log.info(
        f"Proxy started: region={region} routing={routing} rate_scale={rate_scale} keys={len(keys)}"
    )
    yield
    pool.close()
    cache.stop()
    log.info("Proxy shut down")


app = FastAPI(title="lol-genius riot-proxy", lifespan=lifespan)


async def _cached_get(request: Request, namespace: str, cache_key: str, url: str) -> JSONResponse:
    cache: ProxyCache = request.app.state.cache
    pool: KeyPool = request.app.state.pool

    hit, value = cache.get(namespace, cache_key)
    if hit:
        if isinstance(value, tuple):
            data, cached_key_index = value
        else:
            data, cached_key_index = value, None
        resp = {"data": data, "cached": True}
        if cached_key_index is not None:
            resp["key_index"] = cached_key_index
        return JSONResponse(resp)

    raw_key_index = request.headers.get("X-Key-Index")
    key_index = int(raw_key_index) if raw_key_index is not None else None
    priority = request.headers.get("X-Priority", "normal")

    try:
        result, used_key_index = await asyncio.to_thread(pool.get, url, key_index, priority)
    except APIKeyExpiredError:
        return JSONResponse({"error": "All API keys expired"}, status_code=503)
    except BadRequestError as e:
        log.warning(f"Bad request (not cached): {e}")
        return JSONResponse({"error": "bad_request", "detail": str(e)}, status_code=400)
    except Exception:
        log.exception("Upstream error")
        return JSONResponse({"error": "upstream_error"}, status_code=502)

    cache.set(namespace, cache_key, (result, used_key_index), CACHE_TTLS.get(namespace, 3600))
    return JSONResponse({"data": result, "cached": False, "key_index": used_key_index})


@app.get("/riot/v1/health")
async def health(request: Request):
    cache: ProxyCache = request.app.state.cache
    pool: KeyPool = request.app.state.pool
    key_status = pool.status()
    healthy_count = sum(1 for k in key_status if k["healthy"])
    return {
        "status": "ok" if healthy_count > 0 else "degraded",
        "keys": {
            "healthy": healthy_count,
            "total": len(key_status),
            "detail": key_status,
        },
        "cache": cache.stats(),
    }


@app.get("/riot/v1/rate-usage")
async def rate_usage(request: Request):
    pool: KeyPool = request.app.state.pool
    return pool.aggregate_usage()


@app.post("/riot/v1/reload-keys")
async def reload_keys(request: Request):
    rate_scale = float(os.environ.get("LOL_GENIUS_RATE_SCALE", "1.0"))

    try:
        load_dotenv(override=True)
        new_keys = _load_api_keys()
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    old_pool: KeyPool = request.app.state.pool
    old_count = len(old_pool._keys)

    new_pool = KeyPool(new_keys, rate_scale=rate_scale)
    old_pool.close()

    request.app.state.pool = new_pool

    cache: ProxyCache = request.app.state.cache
    flushed = cache.clear()

    log.info(f"Keys reloaded: {old_count} -> {len(new_keys)}, cache flushed ({flushed} entries)")
    return {"old_keys": old_count, "new_keys": len(new_keys), "cache_flushed": flushed}


@app.get("/riot/v1/summoner/by-puuid/{puuid}")
async def summoner_by_puuid(request: Request, puuid: str):
    url = f"{request.app.state.region_url}/lol/summoner/v4/summoners/by-puuid/{puuid}"
    return await _cached_get(request, "summoner", f"puuid:{puuid}", url)


@app.get("/riot/v1/summoner/{summoner_id}")
async def summoner_by_id(request: Request, summoner_id: str):
    url = f"{request.app.state.region_url}/lol/summoner/v4/summoners/{summoner_id}"
    return await _cached_get(request, "summoner", f"id:{summoner_id}", url)


@app.get("/riot/v1/league/entries/{tier}/{division}")
async def league_entries(
    request: Request,
    tier: str,
    division: str,
    page: int = Query(1),
):
    url = (
        f"{request.app.state.region_url}/lol/league/v4/entries/RANKED_SOLO_5x5"
        f"/{tier}/{division}?page={page}"
    )
    return await _cached_get(request, "league_entries", f"{tier}:{division}:{page}", url)


@app.get("/riot/v1/league/by-puuid/{puuid}")
async def league_by_puuid(request: Request, puuid: str):
    url = f"{request.app.state.region_url}/lol/league/v4/entries/by-puuid/{puuid}"
    return await _cached_get(request, "league_by_puuid", puuid, url)


@app.get("/riot/v1/league/by-summoner/{summoner_id}")
async def league_by_summoner(request: Request, summoner_id: str):
    url = f"{request.app.state.region_url}/lol/league/v4/entries/by-summoner/{summoner_id}"
    return await _cached_get(request, "league_by_summoner", summoner_id, url)


@app.get("/riot/v1/match/ids/{puuid}")
async def match_ids(
    request: Request,
    puuid: str,
    start: int = Query(0),
    count: int = Query(20),
    queue: int = Query(420),
    start_time: int | None = Query(None),
):
    params = f"start={start}&count={count}&queue={queue}"
    if start_time is not None:
        params += f"&startTime={start_time}"
    url = f"{request.app.state.routing_url}/lol/match/v5/matches/by-puuid/{puuid}/ids?{params}"
    cache_key = f"{puuid}:{start}:{count}:{queue}:{start_time}"
    return await _cached_get(request, "match_ids", cache_key, url)


@app.get("/riot/v1/match/{match_id}/timeline")
async def match_timeline(request: Request, match_id: str):
    url = f"{request.app.state.routing_url}/lol/match/v5/matches/{match_id}/timeline"
    return await _cached_get(request, "match", f"{match_id}:timeline", url)


@app.get("/riot/v1/match/{match_id}")
async def match(request: Request, match_id: str):
    url = f"{request.app.state.routing_url}/lol/match/v5/matches/{match_id}"
    return await _cached_get(request, "match", match_id, url)


@app.get("/riot/v1/mastery/by-puuid/{puuid}/by-champion/{champion_id}")
async def mastery_by_champion(request: Request, puuid: str, champion_id: int):
    url = (
        f"{request.app.state.region_url}/lol/champion-mastery/v4"
        f"/champion-masteries/by-puuid/{puuid}/by-champion/{champion_id}"
    )
    return await _cached_get(request, "mastery", f"{puuid}:{champion_id}", url)


@app.get("/riot/v1/mastery/by-puuid/{puuid}/top")
async def mastery_top(
    request: Request,
    puuid: str,
    count: int = Query(10),
):
    url = (
        f"{request.app.state.region_url}/lol/champion-mastery/v4"
        f"/champion-masteries/by-puuid/{puuid}/top?count={count}"
    )
    return await _cached_get(request, "mastery", f"top:{puuid}:{count}", url)


@app.get("/riot/v1/account/by-riot-id/{game_name}/{tag_line}")
async def account_by_riot_id(request: Request, game_name: str, tag_line: str):
    url = (
        f"{request.app.state.routing_url}/riot/account/v1"
        f"/accounts/by-riot-id/{game_name}/{tag_line}"
    )
    return await _cached_get(request, "account", f"{game_name}:{tag_line}", url)


@app.get("/riot/v1/spectator/by-puuid/{puuid}")
async def spectator_by_puuid(request: Request, puuid: str):
    url = f"{request.app.state.region_url}/lol/spectator/v5/active-games/by-summoner/{puuid}"
    return await _cached_get(request, "spectator", f"spectator:{puuid}", url)
