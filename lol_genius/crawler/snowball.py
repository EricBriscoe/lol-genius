from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

from lol_genius.api.client import APIKeyExpiredError
from lol_genius.api.ddragon import DataDragon
from lol_genius.api.riot_api import RiotAPI
from lol_genius.config import Config
from lol_genius.crawler.parse import parse_match, parse_patch
from lol_genius.db.queries import MatchDB

log = logging.getLogger(__name__)

_DOCKER = os.environ.get("LOL_GENIUS_DOCKER") == "1"
_THREAD_POOL_SIZE = 4

_CHECKPOINTS = [1_000, 5_000, 15_000, 25_000, 50_000, 100_000]
_ROLLING_WINDOW = 300
_BAD_REQUEST_ABORT_THRESHOLD = 3


class _BadRequestBatchError(Exception):
    pass


def _check_bad_request_abort(consecutive: int) -> None:
    if consecutive >= _BAD_REQUEST_ABORT_THRESHOLD:
        log.error(
            f"Aborting: {consecutive} consecutive matches returned all-400 responses. "
            "PUUIDs are likely stale from a previous API key. "
            "Regenerate your Riot API key and re-seed the crawl queue."
        )
        raise SystemExit(1)


class _RollingRate:
    def __init__(self, window: float = _ROLLING_WINDOW):
        self._window = window
        self._events: deque[float] = deque()

    def record(self, count: int = 1) -> None:
        now = time.monotonic()
        for _ in range(count):
            self._events.append(now)

    def rate_per_hour(self) -> float:
        self._prune()
        if len(self._events) < 2:
            return 0.0
        span = self._events[-1] - self._events[0]
        if span <= 0:
            return 0.0
        return len(self._events) / (span / 3600)

    def _prune(self) -> None:
        cutoff = time.monotonic() - self._window
        while self._events and self._events[0] < cutoff:
            self._events.popleft()


def _format_duration(hours: float) -> str:
    if hours < 1:
        return f"{hours * 60:.0f}m"
    if hours < 24:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


def _format_eta(current: int, rate_hr: float, target: int) -> str:
    if rate_hr <= 0:
        return ""
    for cp in _CHECKPOINTS:
        if current < cp <= target:
            remaining = cp - current
            return f"ETA {cp // 1000}K: {_format_duration(remaining / rate_hr)}"
    remaining = target - current
    return f"ETA target: {_format_duration(remaining / rate_hr)}"


class _GracefulStop:
    def __init__(self):
        self._stop = threading.Event()
        self._original_sigint = None
        self._original_sigterm = None

    def install(self):
        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, self._handle)
        signal.signal(signal.SIGTERM, self._handle)

    def _handle(self, signum, frame):
        if self._stop.is_set():
            log.warning("Force quit requested. Exiting immediately.")
            raise SystemExit(1)
        log.info("Graceful shutdown requested. Finishing current player...")
        self._stop.set()

    def should_stop(self) -> bool:
        return self._stop.is_set()

    def uninstall(self):
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)


def _auto_seed(api: RiotAPI, db: MatchDB, config: Config) -> None:
    from lol_genius.crawler.seed import seed_accounts

    log.info("Crawl queue empty — auto-seeding from League-V4 entries...")
    added = seed_accounts(api, db, config)
    log.info(f"Auto-seeded {added} accounts")


def _enrich_match_participants(
    api: RiotAPI,
    db: MatchDB,
    participants: list[dict],
    match_start_time: int | None,
) -> bool:
    from lol_genius.crawler.enrich import (
        check_enrich_needed,
        fetch_enrichment,
        write_enrichment,
    )

    start_time_ms = match_start_time * 1000 if match_start_time else None

    work_items: list[tuple[str, str, dict[str, bool]]] = []
    for p in participants:
        puuid = p["puuid"]
        summoner_id = p.get("summoner_id", "")
        needs = check_enrich_needed(db, puuid, summoner_id, start_time_ms=start_time_ms)
        if any(needs.values()):
            work_items.append((puuid, summoner_id, needs))

    if not work_items:
        return True

    results = []
    with ThreadPoolExecutor(max_workers=_THREAD_POOL_SIZE) as pool:
        futures = {
            pool.submit(
                fetch_enrichment, api, puuid, sid, needs, start_time=match_start_time
            ): puuid
            for puuid, sid, needs in work_items
        }
        all_ok = True
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except APIKeyExpiredError:
                raise
            except Exception as e:
                log.warning(f"Enrich failed for {futures[future]}: {e}")
                all_ok = False

    for result in results:
        write_enrichment(db, result)

    if results and all(r.bad_request for r in results):
        raise _BadRequestBatchError(
            f"All {len(results)} enrichment requests returned 400"
        )

    return all_ok


def drain_unenriched(
    api: RiotAPI,
    database_url: str,
    config: Config,
    stopper: _GracefulStop,
    batch_size: int = 200,
) -> int:
    match_start_time: int | None = None
    if config.crawl_lookback_days > 0:
        match_start_time = int(time.time()) - config.crawl_lookback_days * 86400

    db = MatchDB(database_url)
    enrichment_stats = db.get_enrichment_stats()
    unenriched_total = enrichment_stats["total"] - enrichment_stats["enriched"]

    if unenriched_total <= 0:
        db.close()
        return 0

    enriched_count = 0
    consecutive_bad_request = 0

    if _DOCKER:
        rolling = _RollingRate()
        last_log_time = time.monotonic()
        last_log_count = 0
        log.info(f"Draining {unenriched_total:,} unenriched matches")
    else:
        from tqdm import tqdm

        pbar = tqdm(total=unenriched_total, desc="Enriching", unit="match")

    db.begin_batch()

    try:
        while not stopper.should_stop():
            match_ids = db.get_unenriched_matches(limit=batch_size)
            if not match_ids:
                break

            batch_successes = 0
            for match_id in match_ids:
                if stopper.should_stop():
                    break

                participants = db.get_participants_for_match(match_id)

                all_ok = True
                try:
                    all_ok = _enrich_match_participants(
                        api, db, participants, match_start_time
                    )
                    consecutive_bad_request = 0
                except _BadRequestBatchError:
                    consecutive_bad_request += 1
                    db.flush()
                    _check_bad_request_abort(consecutive_bad_request)
                    continue
                except APIKeyExpiredError:
                    db.flush()
                    if not _DOCKER:
                        pbar.close()
                    raise

                if all_ok:
                    db.mark_match_enriched(match_id)
                    enriched_count += 1
                    batch_successes += 1

                db.flush()

                if _DOCKER:
                    rolling.record()
                    now = time.monotonic()
                    if (
                        enriched_count - last_log_count >= 10
                        or now - last_log_time >= 60
                    ):
                        rate_hr = rolling.rate_per_hour()
                        remaining = unenriched_total - enriched_count
                        eta_str = (
                            f"~{_format_duration(remaining / rate_hr)}"
                            if rate_hr > 0
                            else "?"
                        )
                        used, budget = api.rate_window_usage()
                        log.info(
                            "Enriching %s | %d done"
                            " | %.0f/hr | ETA %s"
                            " | API %d/%d req/2min",
                            f"{unenriched_total:,}",
                            enriched_count,
                            rate_hr, eta_str, used, budget,
                        )
                        last_log_count = enriched_count
                        last_log_time = now
                else:
                    pbar.update(1)

            if batch_successes == 0:
                log.warning(
                    "Full batch yielded 0 successes — breaking to avoid infinite loop"
                )
                break
    finally:
        db.end_batch()
        db.close()

    if not _DOCKER:
        pbar.close()

    log.info(f"Drain complete: enriched {enriched_count:,} matches")
    return enriched_count


def _crawl_batch(
    api: RiotAPI,
    database_url: str,
    config: Config,
    stopper: _GracefulStop,
    match_start_time: int | None,
    puuid_limit: int = 50,
    patch_filter: str | None = None,
    crawl_start_time: float | None = None,
    initial_match_count: int = 0,
    tier_weights: dict[str, int] | None = None,
) -> int:
    db = MatchDB(database_url)
    puuids = db.claim_pending_puuids(limit=puuid_limit, tier_weights=tier_weights)
    if not puuids:
        _auto_seed(api, db, config)
        puuids = db.claim_pending_puuids(limit=puuid_limit, tier_weights=tier_weights)
        if not puuids:
            db.close()
            log.warning("Crawl queue still empty after auto-seed. Stopping.")
            return 0

    matches_added = 0
    puuids_processed = 0
    consecutive_bad_request = 0
    batch_start = time.monotonic()
    last_batch_log = batch_start
    rolling = _RollingRate()
    db.begin_batch()

    try:
        for puuid in puuids:
            if stopper.should_stop():
                break

            match_ids = api.get_match_ids(
                puuid, count=20, queue=420, start_time=match_start_time
            )

            for match_id in match_ids:
                if db.match_exists(match_id):
                    continue

                match_data = api.get_match(match_id)
                if not match_data or not _is_valid_match(
                    match_data, config, patch_override=patch_filter
                ):
                    continue

                parsed = parse_match(match_data)
                if not parsed:
                    continue

                match_row, participants, bans, objectives = parsed
                raw_json = None
                try:
                    raw_json = json.dumps(match_data)
                except Exception:
                    pass
                db.insert_match(
                    match_row,
                    participants,
                    bans=bans,
                    objectives=objectives,
                    raw_json=raw_json,
                )
                other_puuids = [p["puuid"] for p in participants if p["puuid"] != puuid]
                seed_rank = db.get_latest_rank(puuid)
                seed_tier = seed_rank["tier"] if seed_rank else "UNKNOWN"
                db.add_puuids_to_queue(other_puuids, tier=seed_tier)
                db.flush()
                matches_added += 1
                rolling.record()

                try:
                    all_ok = _enrich_match_participants(
                        api, db, participants, match_start_time
                    )
                    consecutive_bad_request = 0
                except _BadRequestBatchError:
                    consecutive_bad_request += 1
                    db.flush()
                    _check_bad_request_abort(consecutive_bad_request)
                    continue
                except APIKeyExpiredError:
                    db.flush()
                    raise

                if all_ok:
                    db.mark_match_enriched(match_id)
                db.flush()

                if _DOCKER:
                    now = time.monotonic()
                    if now - last_batch_log >= 60:
                        total_added = initial_match_count + matches_added
                        rate_hr = rolling.rate_per_hour()
                        used, budget = api.rate_window_usage()
                        eta = _format_eta(total_added, rate_hr, config.match_count)
                        log.info(
                            "Crawl batch: %d/%d PUUIDs"
                            " | %d new matches (%s total)"
                            " | %.0f/hr | %s"
                            " | API %d/%d req/2min",
                            puuids_processed, len(puuids),
                            matches_added, f"{total_added:,}",
                            rate_hr, eta, used, budget,
                        )
                        last_batch_log = now

            db.mark_puuid_done(puuid)
            db.flush()
            puuids_processed += 1
    finally:
        db.end_batch()
        db.close()

    return matches_added


def crawl_matches(
    api: RiotAPI, database_url: str, config: Config, ddragon: DataDragon | None = None
) -> None:
    from lol_genius.crawler.planner import (
        assess_data_quality,
        log_assessment,
        plan_next_action,
    )
    from lol_genius.crawler.seed import seed_tier

    stopper = _GracefulStop()
    stopper.install()

    db = MatchDB(database_url)
    recovered = db.recover_stuck_processing()
    if recovered:
        log.info(f"Recovered {recovered} stuck PUUIDs from previous interrupted run")

    target = config.match_count
    start_time = time.monotonic()
    match_start_time: int | None = None
    if config.crawl_lookback_days > 0:
        match_start_time = int(time.time()) - config.crawl_lookback_days * 86400
    current = db.get_match_count()
    last_log_count = current
    db.close()

    if ddragon is None:
        ddragon = DataDragon(config.ddragon_cache)

    if _DOCKER:
        log.info(f"Crawl target: {target:,} matches. Currently: {current:,}")
        pbar = None
    else:
        from tqdm import tqdm

        pbar = tqdm(total=target, initial=current, desc="Crawling", unit="match")

    last_log_time = time.monotonic()
    progress_rolling = _RollingRate()

    def _update_progress() -> None:
        nonlocal current, last_log_count, last_log_time
        db = MatchDB(database_url)
        prev = current
        current = db.get_match_count()
        db.close()
        delta = current - prev
        if delta > 0:
            progress_rolling.record(delta)
        if _DOCKER:
            now = time.monotonic()
            if current - last_log_count >= 10 or now - last_log_time >= 60:
                rate_hr = progress_rolling.rate_per_hour()
                eta = _format_eta(current, rate_hr, target)
                log.info(
                    "Progress: %s / %s matches (%.1f%%)"
                    " | %.0f/hr | %s",
                    f"{current:,}", f"{target:,}",
                    current / target * 100, rate_hr, eta,
                )
                last_log_count = current
                last_log_time = now
        elif pbar:
            rate_hr = progress_rolling.rate_per_hour()
            used, budget = api.rate_window_usage()
            pbar.n = current
            pbar.set_postfix_str(f"{rate_hr:.0f}/hr | API {used}/{budget}")
            pbar.refresh()

    try:
        while current < target and not stopper.should_stop():
            db = MatchDB(database_url)
            metrics = assess_data_quality(db, ddragon)
            db.close()

            action = plan_next_action(metrics, config)
            log_assessment(metrics, action)

            if action.action == "enrich":
                drain_unenriched(api, database_url, config, stopper, batch_size=200)

            elif action.action == "reseed":
                db = MatchDB(database_url)
                seed_tier(api, db, config, tier=action.tier)
                db.close()
                _crawl_batch(
                    api,
                    database_url,
                    config,
                    stopper,
                    match_start_time,
                    puuid_limit=50,
                    crawl_start_time=start_time,
                    initial_match_count=current,
                    tier_weights=metrics.tier_counts,
                )

            else:
                _crawl_batch(
                    api,
                    database_url,
                    config,
                    stopper,
                    match_start_time,
                    puuid_limit=50,
                    patch_filter=action.patch,
                    crawl_start_time=start_time,
                    initial_match_count=current,
                    tier_weights=metrics.tier_counts,
                )

            _update_progress()

    except APIKeyExpiredError:
        log.error("API key expired after all backoff retries. Container will restart.")
        raise SystemExit(1)
    finally:
        if pbar:
            pbar.close()
        stopper.uninstall()

    db = MatchDB(database_url)
    total = db.get_match_count()
    db.close()
    if stopper.should_stop():
        log.info(
            f"Crawl paused. {total:,} matches collected. Run 'crawl' again to resume."
        )
    elif config.continuous:
        log.info(f"Target reached ({total:,} matches). Entering maintenance mode.")
        _maintenance_loop(api, database_url, config, ddragon, stopper, match_start_time)
    else:
        log.info(f"Crawl complete. {total:,} matches collected.")


def _maintenance_loop(
    api: RiotAPI,
    database_url: str,
    config: Config,
    ddragon: DataDragon,
    stopper: _GracefulStop,
    match_start_time: int | None,
) -> None:
    from lol_genius.crawler.enrich import re_enrich_stale_batch
    from lol_genius.crawler.planner import (
        assess_data_quality,
        log_assessment,
        plan_next_action,
    )
    from lol_genius.crawler.seed import seed_tier

    consecutive_healthy = 0
    last_prune_time = time.monotonic()

    try:
        while not stopper.should_stop():
            db = MatchDB(database_url)
            metrics = assess_data_quality(db, ddragon, maintenance=True)
            db.close()

            action = plan_next_action(
                metrics,
                config,
                maintenance=True,
                consecutive_healthy=consecutive_healthy,
            )
            log_assessment(metrics, action)

            if action.action == "sleep":
                consecutive_healthy += 1
                log.info(
                    f"Sleeping {action.sleep_seconds}s (consecutive healthy: {consecutive_healthy})"
                )
                if stopper._stop.wait(timeout=action.sleep_seconds):
                    break
                continue

            consecutive_healthy = 0

            if action.action == "refresh_ddragon":
                old_version = ddragon.get_latest_version()
                ddragon.invalidate_version_cache()
                new_version = ddragon.get_latest_version()
                ddragon.fetch_champion_data(new_version)
                if old_version != new_version:
                    log.info(f"New patch detected: {old_version} -> {new_version}")
                else:
                    log.info(f"DDragon version unchanged: {new_version}")

                now = time.monotonic()
                if now - last_prune_time >= config.ddragon_check_interval:
                    db = MatchDB(database_url)
                    pruned = db.prune_old_ranks()
                    db.close()
                    if pruned:
                        log.info(f"Pruned {pruned} old rank history rows")
                    last_prune_time = now

            elif action.action == "enrich":
                drain_unenriched(api, database_url, config, stopper, batch_size=200)

            elif action.action == "re_enrich":
                db = MatchDB(database_url)
                db.begin_batch()
                stale_puuids = db.get_stale_enrichment_puuids(
                    hours=config.stale_enrichment_hours, limit=50
                )
                if stale_puuids:
                    refreshed = re_enrich_stale_batch(api, db, stale_puuids)
                    log.info(f"Re-enriched {refreshed} stale players")
                db.end_batch()
                db.close()

            elif action.action == "reseed":
                db = MatchDB(database_url)
                seed_tier(api, db, config, tier=action.tier)
                db.close()
                _crawl_batch(
                    api,
                    database_url,
                    config,
                    stopper,
                    match_start_time,
                    puuid_limit=50,
                    tier_weights=metrics.tier_counts,
                )

            else:
                _crawl_batch(
                    api,
                    database_url,
                    config,
                    stopper,
                    match_start_time,
                    puuid_limit=50,
                    patch_filter=action.patch,
                    tier_weights=metrics.tier_counts,
                )

    except APIKeyExpiredError:
        log.error("API key expired during maintenance. Container will restart.")
        raise SystemExit(1)

    log.info("Maintenance mode stopped.")


def _is_valid_match(
    match_data: dict, config: Config, patch_override: str | None = None
) -> bool:
    info = match_data.get("info", {})

    if info.get("queueId") != 420:
        return False

    if info.get("gameDuration", 0) < 300:
        return False

    effective_patch = patch_override or config.patch_filter
    if effective_patch:
        patch = parse_patch(info.get("gameVersion", ""))
        if patch != effective_patch:
            return False

    return True
