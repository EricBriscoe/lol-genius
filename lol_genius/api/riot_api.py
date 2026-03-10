from __future__ import annotations

import logging

from .client import RiotHTTPClient

log = logging.getLogger(__name__)


def _coerce_list(result, context: str) -> list[dict]:
    if isinstance(result, list):
        return result
    if result is not None:
        log.warning("Expected list from %s, got %s", context, type(result).__name__)
    return []


class RiotAPI:
    def __init__(
        self,
        client: RiotHTTPClient,
        region: str,
        routing: str,
        priority: str = "normal",
    ):
        self.client = client
        self.region_url = f"https://{region}.api.riotgames.com"
        self.routing_url = f"https://{routing}.api.riotgames.com"
        self.priority = priority

    def _get(self, url: str) -> dict | list | None:
        return self.client.get(url, priority=self.priority)

    def get_summoner_by_puuid(self, puuid: str) -> dict | None:
        return self._get(f"{self.region_url}/lol/summoner/v4/summoners/by-puuid/{puuid}")

    def get_summoner_by_id(self, summoner_id: str) -> dict | None:
        return self._get(f"{self.region_url}/lol/summoner/v4/summoners/{summoner_id}")

    def get_account_by_riot_id(self, game_name: str, tag_line: str) -> dict | None:
        return self._get(
            f"{self.routing_url}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        )

    def get_league_entries(self, tier: str, division: str, page: int = 1) -> list[dict]:
        result = self._get(
            f"{self.region_url}/lol/league/v4/entries/RANKED_SOLO_5x5/{tier}/{division}?page={page}"
        )
        return _coerce_list(result, "get_league_entries")

    def get_league_by_summoner(self, summoner_id: str) -> list[dict]:
        result = self._get(f"{self.region_url}/lol/league/v4/entries/by-summoner/{summoner_id}")
        return _coerce_list(result, "get_league_by_summoner")

    def get_league_by_puuid(self, puuid: str) -> list[dict]:
        result = self._get(f"{self.region_url}/lol/league/v4/entries/by-puuid/{puuid}")
        return _coerce_list(result, "get_league_by_puuid")

    def get_match_ids(
        self,
        puuid: str,
        start: int = 0,
        count: int = 20,
        queue: int = 420,
        start_time: int | None = None,
    ) -> list[str]:
        params = f"start={start}&count={count}&queue={queue}"
        if start_time is not None:
            params += f"&startTime={start_time}"
        result = self._get(f"{self.routing_url}/lol/match/v5/matches/by-puuid/{puuid}/ids?{params}")
        return _coerce_list(result, "get_match_ids")

    def get_match(self, match_id: str) -> dict | None:
        return self._get(f"{self.routing_url}/lol/match/v5/matches/{match_id}")

    def get_champion_mastery(self, puuid: str, champion_id: int) -> dict | None:
        return self._get(
            f"{self.region_url}/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champion_id}"
        )

    def get_top_masteries(self, puuid: str, count: int = 10) -> list[dict]:
        result = self._get(
            f"{self.region_url}/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?count={count}"
        )
        return _coerce_list(result, "get_top_masteries")

    def rate_window_usage(self) -> tuple[int, int]:
        return self.client.rate_window_usage()

    def close(self):
        self.client.close()
