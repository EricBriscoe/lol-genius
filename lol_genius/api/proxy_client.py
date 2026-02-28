from __future__ import annotations

import logging
import time

import httpx

from lol_genius.api.client import APIKeyExpiredError

log = logging.getLogger(__name__)


class ProxyClient:
    def __init__(self, proxy_url: str):
        self.base = proxy_url.rstrip("/") + "/riot/v1"
        self.client = httpx.Client(timeout=120.0)
        self._puuid_keys: dict[str, int] = {}

    def _get(self, path: str, max_retries: int = 3, key_index: int | None = None) -> tuple[dict | list | None, int | None]:
        url = f"{self.base}{path}"
        headers = {}
        if key_index is not None:
            headers["X-Key-Index"] = str(key_index)
        for attempt in range(max_retries):
            try:
                resp = self.client.get(url, headers=headers)
            except httpx.RequestError as e:
                log.warning(f"Proxy request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

            if resp.status_code == 200:
                body = resp.json()
                if isinstance(body, dict) and "data" in body:
                    raw_ki = body.get("key_index")
                    ki = int(raw_ki) if raw_ki is not None else None
                    return body["data"], ki
                return body, None

            if resp.status_code == 503:
                log.error("Proxy reports API key expired")
                raise APIKeyExpiredError("Riot API key expired (proxy 503)")

            if resp.status_code >= 500:
                wait = min(2 ** attempt, 30)
                log.warning(f"Proxy {resp.status_code}, retrying in {wait}s")
                time.sleep(wait)
                continue

            body = ""
            try:
                body = resp.text[:500]
            except Exception:
                pass
            log.error(f"Proxy {resp.status_code} for {url}: {body}")
            return None, None

        log.error(f"Max retries exceeded for proxy: {path}")
        return None, None

    def _get_list(self, path: str, key_index: int | None = None) -> list[dict]:
        result, _ = self._get(path, key_index=key_index)
        return result if isinstance(result, list) else []

    def _key_for_puuid(self, puuid: str) -> int | None:
        return self._puuid_keys.get(puuid)

    def _store_puuid_key(self, puuid: str, key_index: int | None) -> None:
        if key_index is not None:
            self._puuid_keys[puuid] = key_index

    def get_summoner_by_puuid(self, puuid: str) -> dict | None:
        data, _ = self._get(f"/summoner/by-puuid/{puuid}", key_index=self._key_for_puuid(puuid))
        return data

    def get_summoner_by_id(self, summoner_id: str) -> dict | None:
        data, _ = self._get(f"/summoner/{summoner_id}")
        return data

    def get_account_by_riot_id(self, game_name: str, tag_line: str) -> dict | None:
        data, ki = self._get(f"/account/by-riot-id/{game_name}/{tag_line}")
        if isinstance(data, dict) and data.get("puuid"):
            self._store_puuid_key(data["puuid"], ki)
        return data

    def get_league_entries(self, tier: str, division: str, page: int = 1) -> list[dict]:
        return self._get_list(f"/league/entries/{tier}/{division}?page={page}")

    def get_league_by_summoner(self, summoner_id: str) -> list[dict]:
        return self._get_list(f"/league/by-summoner/{summoner_id}")

    def get_league_by_puuid(self, puuid: str) -> list[dict]:
        return self._get_list(f"/league/by-puuid/{puuid}", key_index=self._key_for_puuid(puuid))

    def get_match_ids(
        self, puuid: str, start: int = 0, count: int = 20,
        queue: int = 420, start_time: int | None = None,
    ) -> list[str]:
        params = f"?start={start}&count={count}&queue={queue}"
        if start_time is not None:
            params += f"&start_time={start_time}"
        result, ki = self._get(f"/match/ids/{puuid}{params}")
        if isinstance(result, list):
            self._store_puuid_key(puuid, ki)
            return result
        return []

    def get_match(self, match_id: str) -> dict | None:
        data, ki = self._get(f"/match/{match_id}")
        if isinstance(data, dict) and ki is not None:
            info = data.get("info", {})
            for p in info.get("participants", []):
                puuid = p.get("puuid")
                if puuid:
                    self._store_puuid_key(puuid, ki)
        return data

    def get_champion_mastery(self, puuid: str, champion_id: int) -> dict | None:
        data, _ = self._get(f"/mastery/by-puuid/{puuid}/by-champion/{champion_id}", key_index=self._key_for_puuid(puuid))
        return data

    def get_top_masteries(self, puuid: str, count: int = 10) -> list[dict]:
        return self._get_list(f"/mastery/by-puuid/{puuid}/top?count={count}", key_index=self._key_for_puuid(puuid))

    def get_active_game(self, puuid: str) -> dict | None:
        data, _ = self._get(f"/spectator/by-puuid/{puuid}", key_index=self._key_for_puuid(puuid))
        return data

    def rate_window_usage(self) -> tuple[int, int]:
        try:
            resp = self.client.get(f"{self.base}/rate-usage", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("total_used", 0), data.get("total_budget", 0)
        except httpx.RequestError:
            pass
        return 0, 0

    def close(self):
        self.client.close()
