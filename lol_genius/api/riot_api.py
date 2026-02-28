from __future__ import annotations

from .client import RiotHTTPClient


class RiotAPI:
    def __init__(self, client: RiotHTTPClient, region: str, routing: str):
        self.client = client
        self.region_url = f"https://{region}.api.riotgames.com"
        self.routing_url = f"https://{routing}.api.riotgames.com"

    def get_summoner_by_puuid(self, puuid: str) -> dict | None:
        return self.client.get(
            f"{self.region_url}/lol/summoner/v4/summoners/by-puuid/{puuid}"
        )

    def get_summoner_by_id(self, summoner_id: str) -> dict | None:
        return self.client.get(
            f"{self.region_url}/lol/summoner/v4/summoners/{summoner_id}"
        )

    def get_account_by_riot_id(self, game_name: str, tag_line: str) -> dict | None:
        return self.client.get(
            f"{self.routing_url}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        )

    def get_league_entries(self, tier: str, division: str, page: int = 1) -> list[dict]:
        result = self.client.get(
            f"{self.region_url}/lol/league/v4/entries/RANKED_SOLO_5x5/{tier}/{division}?page={page}"
        )
        return result if isinstance(result, list) else []

    def get_league_by_summoner(self, summoner_id: str) -> list[dict]:
        result = self.client.get(
            f"{self.region_url}/lol/league/v4/entries/by-summoner/{summoner_id}"
        )
        return result if isinstance(result, list) else []

    def get_league_by_puuid(self, puuid: str) -> list[dict]:
        result = self.client.get(
            f"{self.region_url}/lol/league/v4/entries/by-puuid/{puuid}"
        )
        return result if isinstance(result, list) else []

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
        result = self.client.get(
            f"{self.routing_url}/lol/match/v5/matches/by-puuid/{puuid}/ids?{params}"
        )
        return result if isinstance(result, list) else []

    def get_match(self, match_id: str) -> dict | None:
        return self.client.get(
            f"{self.routing_url}/lol/match/v5/matches/{match_id}"
        )

    def get_champion_mastery(self, puuid: str, champion_id: int) -> dict | None:
        return self.client.get(
            f"{self.region_url}/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champion_id}"
        )

    def get_top_masteries(self, puuid: str, count: int = 10) -> list[dict]:
        result = self.client.get(
            f"{self.region_url}/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?count={count}"
        )
        return result if isinstance(result, list) else []

    def rate_window_usage(self) -> tuple[int, int]:
        return self.client.rate_window_usage()

    def close(self):
        self.client.close()
