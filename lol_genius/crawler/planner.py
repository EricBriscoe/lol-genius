from __future__ import annotations

import logging
from dataclasses import dataclass

from lol_genius.api.ddragon import DataDragon
from lol_genius.config import Config
from lol_genius.crawler.parse import parse_patch
from lol_genius.db.queries import MatchDB

log = logging.getLogger(__name__)

ENRICHMENT_THRESHOLD = 0.95
CURRENT_PATCH_THRESHOLD = 0.80
TIER_BALANCE_THRESHOLD = 0.30


@dataclass
class DataMetrics:
    total_matches: int
    enriched_matches: int
    enrichment_ratio: float
    current_patch: str
    current_patch_matches: int
    current_patch_ratio: float
    tier_counts: dict[str, int]
    tier_balance_ratio: float
    weakest_tier: str | None
    queue_depth: int
    stale_rank_count: int = 0
    total_enriched_players: int = 0
    stale_ratio: float = 0.0
    seconds_since_ddragon_check: float = 0.0


@dataclass
class CrawlAction:
    action: str
    reason: str
    patch: str | None = None
    tier: str | None = None
    sleep_seconds: int = 0


STALE_ENRICHMENT_THRESHOLD = 0.10


def assess_data_quality(
    db: MatchDB, ddragon: DataDragon, maintenance: bool = False
) -> DataMetrics:
    enrichment = db.get_enrichment_stats()
    total = enrichment["total"]
    enriched = enrichment["enriched"]
    enrichment_ratio = enriched / total if total > 0 else 1.0

    current_patch = parse_patch(ddragon.get_latest_version())

    patch_dist = db.get_patch_distribution()
    current_patch_matches = patch_dist.get(current_patch, 0)
    current_patch_ratio = current_patch_matches / total if total > 0 else 0.0

    tier_counts = db.get_rank_distribution()
    non_zero = {t: c for t, c in tier_counts.items() if c > 0}
    if len(non_zero) >= 2:
        tier_balance_ratio = min(non_zero.values()) / max(non_zero.values())
        weakest_tier = min(non_zero, key=non_zero.get)
    else:
        tier_balance_ratio = 1.0
        weakest_tier = None

    queue_depth = db.get_queue_depth()

    stale_rank_count = 0
    total_enriched_players = 0
    stale_ratio = 0.0
    ddragon_check_seconds = ddragon.seconds_since_version_check()

    if maintenance:
        stale = db.get_stale_enrichment_counts()
        stale_rank_count = stale["stale_ranks"]
        total_enriched_players = stale["total_enriched"]
        if total_enriched_players > 0:
            stale_ratio = stale_rank_count / total_enriched_players

    return DataMetrics(
        total_matches=total,
        enriched_matches=enriched,
        enrichment_ratio=enrichment_ratio,
        current_patch=current_patch,
        current_patch_matches=current_patch_matches,
        current_patch_ratio=current_patch_ratio,
        tier_counts=tier_counts,
        tier_balance_ratio=tier_balance_ratio,
        weakest_tier=weakest_tier,
        queue_depth=queue_depth,
        stale_rank_count=stale_rank_count,
        total_enriched_players=total_enriched_players,
        stale_ratio=stale_ratio,
        seconds_since_ddragon_check=ddragon_check_seconds,
    )


def plan_next_action(
    metrics: DataMetrics,
    config: Config,
    maintenance: bool = False,
    consecutive_healthy: int = 0,
) -> CrawlAction:
    if maintenance:
        if metrics.seconds_since_ddragon_check >= config.ddragon_check_interval:
            return CrawlAction(
                action="refresh_ddragon", reason="periodic DDragon version check"
            )

    if metrics.enrichment_ratio < ENRICHMENT_THRESHOLD:
        return CrawlAction(
            action="enrich",
            reason=f"enrichment at {metrics.enrichment_ratio:.1%}, need >{ENRICHMENT_THRESHOLD:.0%}",
        )

    if maintenance and metrics.stale_ratio > STALE_ENRICHMENT_THRESHOLD:
        return CrawlAction(
            action="re_enrich",
            reason=f"stale enrichment data: {metrics.stale_ratio:.1%} ({metrics.stale_rank_count} stale ranks)",
        )

    if (
        metrics.total_matches > 0
        and metrics.current_patch_ratio < CURRENT_PATCH_THRESHOLD
    ):
        return CrawlAction(
            action="crawl",
            patch=metrics.current_patch,
            reason=f"current patch ({metrics.current_patch}) at {metrics.current_patch_ratio:.1%}, need >{CURRENT_PATCH_THRESHOLD:.0%}",
        )

    if metrics.weakest_tier and metrics.tier_balance_ratio < TIER_BALANCE_THRESHOLD:
        return CrawlAction(
            action="reseed",
            tier=metrics.weakest_tier,
            reason=f"tier balance {metrics.tier_balance_ratio:.2f}, need >{TIER_BALANCE_THRESHOLD:.2f} — weakest: {metrics.weakest_tier}",
        )

    if not maintenance:
        return CrawlAction(action="crawl", reason="general volume crawl")

    sleep_seconds = min(
        config.maintenance_sleep_base * (2 ** min(consecutive_healthy, 3)),
        config.maintenance_sleep_max,
    )
    return CrawlAction(
        action="sleep",
        reason="all quality metrics satisfied",
        sleep_seconds=sleep_seconds,
    )


def log_assessment(metrics: DataMetrics, action: CrawlAction) -> None:
    tier_str = ", ".join(
        f"{t}: {c}" for t, c in sorted(metrics.tier_counts.items(), key=lambda x: -x[1])
    )
    lines = [
        "",
        "--- Data Quality Assessment ---",
        f"  Matches: {metrics.total_matches:,} (enriched: {metrics.enriched_matches:,}, {metrics.enrichment_ratio:.1%})",
        f"  Current patch: {metrics.current_patch} — {metrics.current_patch_matches:,} matches ({metrics.current_patch_ratio:.1%})",
        f"  Tier balance: {metrics.tier_balance_ratio:.2f} | {tier_str}",
        f"  Queue depth: {metrics.queue_depth:,}",
    ]
    if metrics.total_enriched_players > 0:
        lines.append(
            f"  Staleness: {metrics.stale_ratio:.1%} ({metrics.stale_rank_count} stale ranks) of {metrics.total_enriched_players} players"
        )
    action_line = f"  Action: {action.action.upper()} — {action.reason}"
    if action.sleep_seconds:
        action_line += f" ({action.sleep_seconds}s)"
    lines.append(action_line)
    lines.append("---")
    log.info("\n".join(lines))
