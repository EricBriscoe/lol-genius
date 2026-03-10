from __future__ import annotations

import logging

from tqdm import tqdm

from lol_genius.config import Config
from lol_genius.db.queries import MatchDB

log = logging.getLogger(__name__)

ENTRIES_PER_PAGE = 205


def _extract_puuids(api, entries: list[dict]) -> list[str]:
    puuids = []
    for entry in entries:
        puuid = entry.get("puuid")
        if puuid:
            puuids.append(puuid)
            continue
        summoner_id = entry.get("summonerId")
        if summoner_id:
            resp = api.get_summoner_by_id(summoner_id)
            if resp and isinstance(resp, dict):
                p = resp.get("puuid")
                if p:
                    puuids.append(p)
    return puuids


def _fetch_tier_puuids(api, tier: str, divisions: list[str], target: int) -> list[str]:
    collected: list[str] = []
    page_by_div = {d: 1 for d in divisions}
    exhausted = set()

    while len(collected) < target and len(exhausted) < len(divisions):
        for division in divisions:
            if division in exhausted:
                continue
            if len(collected) >= target:
                break

            page = page_by_div[division]
            entries = api.get_league_entries(tier, division, page)

            if not entries:
                exhausted.add(division)
                continue

            puuids = _extract_puuids(api, entries)
            collected.extend(puuids)
            page_by_div[division] = page + 1

            if len(entries) < ENTRIES_PER_PAGE:
                exhausted.add(division)

    return collected[:target]


def seed_accounts(api, db: MatchDB, config: Config) -> int:
    total_added = 0
    divisions = config.target_divisions
    tiers = config.target_tiers
    per_tier_target = config.seed_pages * ENTRIES_PER_PAGE * len(divisions)

    pbar = tqdm(total=per_tier_target * len(tiers), desc="Seeding accounts", unit="acct")

    for tier in tiers:
        puuids = _fetch_tier_puuids(api, tier, divisions, per_tier_target)
        added = db.add_puuids_to_queue(puuids, tier=tier)
        total_added += added
        pbar.set_postfix(tier=tier, added=total_added)
        pbar.update(len(puuids))

    pbar.close()
    log.info(
        "Seeded %d accounts across %d tiers (%d target per tier)",
        total_added,
        len(tiers),
        per_tier_target,
    )
    return total_added


def seed_tier(api, db: MatchDB, config: Config, tier: str, pages: int = 3) -> int:
    divisions = config.target_divisions
    target = pages * ENTRIES_PER_PAGE * len(divisions)
    puuids = _fetch_tier_puuids(api, tier, divisions, target)
    added = db.add_puuids_to_queue(puuids, tier=tier)
    log.info(f"Reseeded {added} accounts for tier {tier}")
    return added
