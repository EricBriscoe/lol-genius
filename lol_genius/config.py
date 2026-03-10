from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    riot_api_key: str
    region: str
    routing: str
    database_url: str
    ddragon_cache: str
    model_dir: str
    queue_type: str
    target_tiers: list[str]
    target_divisions: list[str]
    patch_filter: str | None
    crawl_lookback_days: int
    match_count: int
    seed_pages: int
    rate_scale: float
    continuous: bool
    stale_enrichment_hours: int
    ddragon_check_interval: int
    maintenance_sleep_base: int
    maintenance_sleep_max: int
    proxy_url: str | None = None


ROUTING_MAP = {
    "na1": "americas",
    "br1": "americas",
    "la1": "americas",
    "la2": "americas",
    "oc1": "americas",
    "euw1": "europe",
    "eun1": "europe",
    "tr1": "europe",
    "ru": "europe",
    "kr": "asia",
    "jp1": "asia",
    "ph2": "asia",
    "sg2": "asia",
    "tw2": "asia",
    "th2": "asia",
    "vn2": "asia",
}


def make_key_loader() -> callable:
    def _load():
        from dotenv import load_dotenv as _ld

        _ld(override=True)
        return os.environ.get("RIOT_API_KEY", "")

    return _load


def load_config(config_path: str = "config.yaml") -> Config:
    load_dotenv()

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    region = os.environ.get("LOL_GENIUS_REGION", raw.get("region", "na1"))
    proxy_url = os.environ.get("RIOT_PROXY_URL", raw.get("proxy_url"))
    api_key = os.environ.get("RIOT_API_KEY", "")
    if not api_key and not proxy_url:
        raise ValueError(
            "RIOT_API_KEY not set and no RIOT_PROXY_URL configured. Add one to .env or export it."
        )

    for d in ["ddragon_cache", "model_dir"]:
        path = Path(raw.get(d, f"data/{d}"))
        path.parent.mkdir(parents=True, exist_ok=True)

    tiers = raw.get("target_tiers", raw.get("target_tier"))
    if isinstance(tiers, str):
        tiers = [tiers]
    if not tiers:
        tiers = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND"]

    database_url = os.environ.get("DATABASE_URL", raw.get("database_url", ""))
    if database_url and not database_url.startswith("postgresql://"):
        raise ValueError(f"database_url must start with postgresql://, got: {database_url[:30]}...")
    if region not in ROUTING_MAP:
        raise ValueError(f"Unknown region '{region}'. Valid: {', '.join(sorted(ROUTING_MAP))}")

    known_tiers = {
        "IRON",
        "BRONZE",
        "SILVER",
        "GOLD",
        "PLATINUM",
        "EMERALD",
        "DIAMOND",
        "MASTER",
        "GRANDMASTER",
        "CHALLENGER",
    }
    valid_divisions = {"I", "II", "III", "IV"}
    divisions = raw.get("target_divisions", ["I", "II", "III", "IV"])
    for t in tiers:
        if t not in known_tiers:
            raise ValueError(f"Unknown tier '{t}'. Valid: {', '.join(sorted(known_tiers))}")
    for d in divisions:
        if d not in valid_divisions:
            raise ValueError(f"Unknown division '{d}'. Valid: {', '.join(sorted(valid_divisions))}")

    return Config(
        riot_api_key=api_key,
        region=region,
        routing=os.environ.get(
            "LOL_GENIUS_ROUTING",
            raw.get("routing", ROUTING_MAP.get(region, "americas")),
        ),
        database_url=database_url,
        ddragon_cache=raw.get("ddragon_cache", "data/ddragon"),
        model_dir=raw.get("model_dir", "data/models"),
        queue_type=raw.get("queue_type", "RANKED_SOLO_5x5"),
        target_tiers=tiers,
        target_divisions=divisions,
        patch_filter=raw.get("patch_filter"),
        crawl_lookback_days=int(raw.get("crawl_lookback_days", 90)),
        match_count=int(raw.get("match_count", 50000)),
        seed_pages=int(raw.get("seed_pages", 5)),
        rate_scale=float(os.getenv("LOL_GENIUS_RATE_SCALE", str(raw.get("rate_scale", 1.0)))),
        continuous=raw.get("continuous", True),
        stale_enrichment_hours=int(raw.get("stale_enrichment_hours", 72)),
        ddragon_check_interval=int(raw.get("ddragon_check_interval", 3600)),
        maintenance_sleep_base=int(raw.get("maintenance_sleep_base", 300)),
        maintenance_sleep_max=int(raw.get("maintenance_sleep_max", 1800)),
        proxy_url=proxy_url,
    )
