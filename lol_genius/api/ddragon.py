from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://ddragon.leagueoflegends.com"

AP_TAGS = {"Mage", "Support"}
AD_TAGS = {"Fighter", "Assassin", "Marksman"}


class DataDragon:
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._champions: dict[int, dict] = {}
        self._version: str | None = None
        self._version_checked_at: float = 0.0

    def get_latest_version(self) -> str:
        if self._version:
            return self._version
        resp = httpx.get(f"{BASE_URL}/api/versions.json", timeout=15)
        resp.raise_for_status()
        self._version = resp.json()[0]
        self._version_checked_at = time.monotonic()
        return self._version

    def invalidate_version_cache(self) -> None:
        self._version = None
        self._champions = {}

    def seconds_since_version_check(self) -> float:
        if self._version_checked_at == 0.0:
            return float("inf")
        return time.monotonic() - self._version_checked_at

    def fetch_champion_data(self, version: str | None = None) -> dict[int, dict]:
        if self._champions:
            return self._champions

        version = version or self.get_latest_version()
        cache_file = self.cache_dir / f"champions_{version}.json"

        if cache_file.exists():
            with open(cache_file) as f:
                self._champions = {int(k): v for k, v in json.load(f).items()}
            return self._champions

        log.info(f"Downloading champion data for patch {version}")
        resp = httpx.get(
            f"{BASE_URL}/cdn/{version}/data/en_US/champion.json", timeout=30
        )
        resp.raise_for_status()
        raw = resp.json()["data"]

        champions = {}
        for name, champ in raw.items():
            key = int(champ["key"])
            champions[key] = {
                "id": champ["id"],
                "name": champ["name"],
                "key": key,
                "tags": champ.get("tags", []),
                "stats": champ.get("stats", {}),
                "info": champ.get("info", {}),
            }

        self._fetch_detailed_stats(version, champions)

        with open(cache_file, "w") as f:
            json.dump({str(k): v for k, v in champions.items()}, f)

        self._champions = champions
        return champions

    def _fetch_detailed_stats(self, version: str, champions: dict[int, dict]) -> None:
        for key, champ in champions.items():
            url = f"{BASE_URL}/cdn/{version}/data/en_US/champion/{champ['id']}.json"
            try:
                resp = httpx.get(url, timeout=15)
                resp.raise_for_status()
                detail = resp.json()["data"][champ["id"]]
                champ["stats"] = detail.get("stats", champ["stats"])
            except (httpx.HTTPError, KeyError) as e:
                log.debug(f"Failed to fetch detail for {champ['id']}: {e}")

    def get_champion(self, champion_id: int) -> dict | None:
        if not self._champions:
            self.fetch_champion_data()
        return self._champions.get(champion_id)

    def classify_damage_type(self, champion_id: int) -> str:
        champ = self.get_champion(champion_id)
        if not champ:
            return "AD"
        tags = set(champ.get("tags", []))
        has_ap = bool(tags & AP_TAGS)
        has_ad = bool(tags & AD_TAGS)
        if has_ap and has_ad:
            return "MIXED"
        if has_ap:
            return "AP"
        return "AD"

    def get_attack_range(self, champion_id: int) -> float:
        champ = self.get_champion(champion_id)
        if not champ:
            return 550.0
        return champ.get("stats", {}).get("attackrange", 550.0)

    def is_melee(self, champion_id: int) -> bool:
        return self.get_attack_range(champion_id) <= 200
