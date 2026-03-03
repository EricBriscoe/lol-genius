from __future__ import annotations

import logging
import threading

from lol_genius.utils import exponential_backoff

log = logging.getLogger(__name__)


def fetch_live_game_data(host: str, port: int) -> dict | None:
    import httpx

    try:
        # verify=False required: League Client API uses a self-signed cert on localhost
        with httpx.Client(verify=False, timeout=5.0) as client:
            resp = client.get(f"https://{host}:{port}/liveclientdata/allgamedata")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        log.debug(f"Live client fetch failed: {e}")
    return None


def _get_player_team(all_players: list[dict], name: str) -> str:
    for player in all_players:
        if player.get("summonerName") == name or player.get("riotId") == name:
            return player.get("team", "")
    return ""


def parse_live_client_data(data: dict) -> dict:
    all_players = data.get("allPlayers", [])
    events = data.get("events", {}).get("Events", [])
    game_time = data.get("gameData", {}).get("gameTime", 0.0)

    blue_kills = red_kills = 0
    blue_cs = red_cs = 0

    for player in all_players:
        team = player.get("team", "")
        scores = player.get("scores", {})
        kills = scores.get("kills", 0)
        cs = scores.get("creepScore", scores.get("cs", 0))
        if team == "ORDER":
            blue_kills += kills
            blue_cs += cs
        else:
            red_kills += kills
            red_cs += cs

    blue_dragons = red_dragons = 0
    blue_barons = red_barons = 0
    blue_towers = red_towers = 0
    blue_heralds = red_heralds = 0
    blue_inhibitors = red_inhibitors = 0
    blue_elder = red_elder = 0
    first_blood_blue = first_tower_blue = first_dragon_blue = 0
    first_blood_set = first_tower_set = first_dragon_set = False

    for event in events:
        name = event.get("EventName", "")
        killer = event.get("KillerName", "")

        if name == "FirstBlood":
            if not first_blood_set:
                first_blood_set = True
                killer_team = _get_player_team(all_players, killer)
                first_blood_blue = 1 if killer_team == "ORDER" else 0

        elif name == "DragonKill":
            killer_team = _get_player_team(all_players, killer)
            if event.get("DragonType") == "Elder":
                if killer_team == "ORDER":
                    blue_elder += 1
                else:
                    red_elder += 1
            else:
                if killer_team == "ORDER":
                    blue_dragons += 1
                    if not first_dragon_set:
                        first_dragon_set = True
                        first_dragon_blue = 1
                else:
                    red_dragons += 1
                    if not first_dragon_set:
                        first_dragon_set = True
                        first_dragon_blue = 0

        elif name == "BaronKill":
            killer_team = _get_player_team(all_players, killer)
            if killer_team == "ORDER":
                blue_barons += 1
            else:
                red_barons += 1

        elif name == "HeraldKill":
            killer_team = _get_player_team(all_players, killer)
            if killer_team == "ORDER":
                blue_heralds += 1
            else:
                red_heralds += 1

        elif name == "TurretKilled":
            killer_team = _get_player_team(all_players, killer)
            if killer_team == "ORDER":
                blue_towers += 1
                if not first_tower_set:
                    first_tower_set = True
                    first_tower_blue = 1
            else:
                red_towers += 1
                if not first_tower_set:
                    first_tower_set = True
                    first_tower_blue = 0

        elif name == "InhibitorKilled":
            killer_team = _get_player_team(all_players, killer)
            if killer_team == "ORDER":
                blue_inhibitors += 1
            else:
                red_inhibitors += 1

    return {
        "game_time": game_time,
        "blue_kills": blue_kills,
        "red_kills": red_kills,
        "kill_diff": blue_kills - red_kills,
        "blue_cs": blue_cs,
        "red_cs": red_cs,
        "cs_diff": blue_cs - red_cs,
        "blue_dragons": blue_dragons,
        "red_dragons": red_dragons,
        "dragon_diff": blue_dragons - red_dragons,
        "blue_barons": blue_barons,
        "red_barons": red_barons,
        "baron_diff": blue_barons - red_barons,
        "blue_towers": blue_towers,
        "red_towers": red_towers,
        "tower_diff": blue_towers - red_towers,
        "blue_heralds": blue_heralds,
        "red_heralds": red_heralds,
        "blue_inhibitors": blue_inhibitors,
        "red_inhibitors": red_inhibitors,
        "inhibitor_diff": blue_inhibitors - red_inhibitors,
        "blue_elder": blue_elder,
        "red_elder": red_elder,
        "elder_diff": blue_elder - red_elder,
        "first_blood_blue": first_blood_blue,
        "first_tower_blue": first_tower_blue,
        "first_dragon_blue": first_dragon_blue,
    }


def _snap_to_snapshot(game_time: float) -> int:
    from lol_genius.features.timeline import SNAPSHOT_SECONDS
    return min(SNAPSHOT_SECONDS, key=lambda t: abs(t - game_time))


def build_live_features(
    game_state: dict,
    pregame_win_prob: float | None = None,
    pregame_summary: dict | None = None,
) -> dict:
    from lol_genius.features.timeline import LIVE_FEATURE_NAMES

    summary = pregame_summary or {}
    mapping = {
        "game_time_seconds": _snap_to_snapshot(game_state.get("game_time", 0)),
        "blue_kills": game_state.get("blue_kills", 0),
        "red_kills": game_state.get("red_kills", 0),
        "kill_diff": game_state.get("kill_diff", 0),
        "blue_cs": game_state.get("blue_cs", 0),
        "red_cs": game_state.get("red_cs", 0),
        "blue_towers": game_state.get("blue_towers", 0),
        "red_towers": game_state.get("red_towers", 0),
        "tower_diff": game_state.get("tower_diff", 0),
        "blue_dragons": game_state.get("blue_dragons", 0),
        "red_dragons": game_state.get("red_dragons", 0),
        "dragon_diff": game_state.get("dragon_diff", 0),
        "blue_barons": game_state.get("blue_barons", 0),
        "red_barons": game_state.get("red_barons", 0),
        "blue_heralds": game_state.get("blue_heralds", 0),
        "red_heralds": game_state.get("red_heralds", 0),
        "blue_inhibitors": game_state.get("blue_inhibitors", 0),
        "red_inhibitors": game_state.get("red_inhibitors", 0),
        "blue_elder": game_state.get("blue_elder", 0),
        "red_elder": game_state.get("red_elder", 0),
        "cs_diff": game_state.get("cs_diff", 0),
        "inhibitor_diff": game_state.get("inhibitor_diff", 0),
        "elder_diff": game_state.get("elder_diff", 0),
        "first_blood_blue": game_state.get("first_blood_blue", 0),
        "first_tower_blue": game_state.get("first_tower_blue", 0),
        "first_dragon_blue": game_state.get("first_dragon_blue", 0),
        "pregame_blue_win_prob": pregame_win_prob if pregame_win_prob is not None else 0.5,
        "avg_rank_diff": summary.get("avg_rank_diff", 0.0),
        "rank_spread_diff": summary.get("rank_spread_diff", 0.0),
        "avg_winrate_diff": summary.get("avg_winrate_diff", 0.0),
        "avg_mastery_diff": summary.get("avg_mastery_diff", 0.0),
        "melee_count_diff": summary.get("melee_count_diff", 0.0),
        "ad_ratio_diff": summary.get("ad_ratio_diff", 0.0),
        "total_games_diff": summary.get("total_games_diff", 0.0),
        "hot_streak_count_diff": summary.get("hot_streak_count_diff", 0.0),
        "veteran_count_diff": summary.get("veteran_count_diff", 0.0),
        "mastery_level7_count_diff": summary.get("mastery_level7_count_diff", 0.0),
        "avg_champ_wr_diff": summary.get("avg_champ_wr_diff", 0.0),
    }
    return {col: mapping.get(col, 0) for col in LIVE_FEATURE_NAMES}


POLL_INTERVAL = 15
MAX_POLL_INTERVAL = 300


class LiveGamePoller:
    def __init__(
        self,
        host: str,
        port: int,
        model_dir: str,
        push_sse_fn,
        pregame_win_prob: float | None = None,
        dsn: str | None = None,
        proxy_url: str | None = None,
        ddragon_cache: str | None = None,
    ):
        self.host = host
        self.port = port
        self.model_dir = model_dir
        self._push_sse = push_sse_fn
        self._pregame_win_prob = pregame_win_prob
        self._dsn = dsn
        self._proxy_url = proxy_url
        self._ddragon_cache = ddragon_cache
        self._pregame_summary: dict | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.current: dict | None = None
        self.history: list[dict] = []
        self.status: str = "waiting"
        self._game_id: int | None = None
        self._last_game_time: float | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "current": self.current,
                "history": list(self.history),
                "status": self.status,
                "pregame_win_prob": self._pregame_win_prob,
            }

    def _enrich_pregame(self, all_players: list[dict]) -> None:
        if not (self._dsn and self._proxy_url and self._ddragon_cache):
            log.warning("Pregame enrichment skipped: missing dsn, proxy_url, or ddragon_cache")
            self._pregame_summary = {}
            return

        try:
            import math

            from lol_genius.api.ddragon import DataDragon
            from lol_genius.api.proxy_client import ProxyClient
            from lol_genius.db.queries import MatchDB
            from lol_genius.features.player import rank_to_numeric
            from lol_genius.features.timeline import compute_pregame_diff_stats

            ddragon = DataDragon(self._ddragon_cache)
            proxy = ProxyClient(self._proxy_url)
            db = MatchDB(self._dsn)

            try:
                champ_wrs = db.get_champion_patch_winrates()

                player_info = []
                for p in all_players:
                    riot_id = p.get("riotId", "")
                    parts = riot_id.rsplit("#", 1)
                    game_name = parts[0] if parts else riot_id
                    tag_line = parts[1] if len(parts) == 2 else ""
                    player_info.append({
                        "key": riot_id,
                        "game_name": game_name,
                        "tag_line": tag_line,
                        "champion_name": p.get("championName", p.get("rawChampionName", "")),
                        "team": p.get("team", "ORDER"),
                    })

                puuid_map = {}
                for p in player_info:
                    result = proxy.get_account_by_riot_id(p["game_name"], p["tag_line"])
                    if result and result.get("puuid"):
                        puuid_map[p["key"]] = result["puuid"]

                if not puuid_map:
                    log.warning("Pregame enrichment: could not resolve any PUUIDs")
                    self._pregame_summary = {}
                    return

                ranks_list, masteries_list = db.get_ranks_and_mastery_by_puuids(list(puuid_map.values()))
                rank_by_puuid = {r["puuid"]: r for r in ranks_list}
                mastery_by_key = {(m["puuid"], m["champion_id"]): m for m in masteries_list}

                blue_ranks, red_ranks = [], []
                blue_wrs, red_wrs = [], []
                blue_masteries, red_masteries = [], []
                blue_melee = red_melee = 0
                blue_ad = red_ad = 0
                blue_total_games, red_total_games = [], []
                blue_hot_streaks = red_hot_streaks = 0
                blue_veterans = red_veterans = 0
                blue_mastery7 = red_mastery7 = 0
                blue_champ_wrs_list, red_champ_wrs_list = [], []

                for p in player_info:
                    puuid = puuid_map.get(p["key"])
                    team = p["team"]
                    champ_id = ddragon.get_champion_id_by_name(p["champion_name"])

                    rank_data = rank_by_puuid.get(puuid) if puuid else None
                    if rank_data and rank_data.get("tier") and rank_data.get("rank"):
                        rank_num = rank_to_numeric(rank_data["tier"], rank_data["rank"], rank_data.get("league_points") or 0)
                        w, losses = rank_data.get("wins") or 0, rank_data.get("losses") or 0
                        wr = w / (w + losses) if (w + losses) > 0 else 0.5
                        if team == "ORDER":
                            blue_ranks.append(rank_num)
                            blue_wrs.append(wr)
                        else:
                            red_ranks.append(rank_num)
                            red_wrs.append(wr)

                    mastery_data = mastery_by_key.get((puuid, champ_id)) if (puuid and champ_id is not None) else None
                    mp = (mastery_data or {}).get("mastery_points") or 0
                    log_mastery = math.log((mp or 0) + 1)
                    if team == "ORDER":
                        blue_masteries.append(log_mastery)
                    else:
                        red_masteries.append(log_mastery)

                    if champ_id is not None:
                        if team == "ORDER":
                            blue_melee += int(ddragon.is_melee(champ_id))
                            blue_ad += int(ddragon.classify_damage_type(champ_id) == "AD")
                        else:
                            red_melee += int(ddragon.is_melee(champ_id))
                            red_ad += int(ddragon.classify_damage_type(champ_id) == "AD")

                    total_games = ((rank_data.get("wins") or 0) + (rank_data.get("losses") or 0)) if rank_data else 0
                    (blue_total_games if team == "ORDER" else red_total_games).append(total_games)

                    if rank_data:
                        if (rank_data.get("hot_streak") or 0) >= 1:
                            if team == "ORDER":
                                blue_hot_streaks += 1
                            else:
                                red_hot_streaks += 1
                        if (rank_data.get("veteran") or 0) >= 1:
                            if team == "ORDER":
                                blue_veterans += 1
                            else:
                                red_veterans += 1

                    if (mastery_data or {}).get("mastery_level", 0) >= 7:
                        if team == "ORDER":
                            blue_mastery7 += 1
                        else:
                            red_mastery7 += 1

                    if champ_id is not None and int(champ_id) in champ_wrs:
                        wr_val = champ_wrs[int(champ_id)]["winrate"]
                        (blue_champ_wrs_list if team == "ORDER" else red_champ_wrs_list).append(wr_val)

                self._pregame_summary = compute_pregame_diff_stats(
                    blue_ranks, red_ranks, blue_wrs, red_wrs,
                    blue_masteries, red_masteries,
                    blue_melee, red_melee, blue_ad, red_ad,
                    blue_total_games=blue_total_games, red_total_games=red_total_games,
                    blue_hot_streaks=blue_hot_streaks, red_hot_streaks=red_hot_streaks,
                    blue_veterans=blue_veterans, red_veterans=red_veterans,
                    blue_mastery7=blue_mastery7, red_mastery7=red_mastery7,
                    blue_champ_wrs=blue_champ_wrs_list, red_champ_wrs=red_champ_wrs_list,
                )
                log.info("Enriched pregame features for game %s", self._game_id)
            finally:
                proxy.close()
                db.close()

        except Exception:
            log.warning("Pregame enrichment failed, using defaults", exc_info=True)
            self._pregame_summary = {}

    def _poll_loop(self) -> None:
        consecutive_failures = 0
        while not self._stop_event.is_set():
            try:
                self._poll()
                consecutive_failures = 0
                wait = POLL_INTERVAL
            except Exception as e:
                log.warning(f"Live game poll error: {e}")
                with self._lock:
                    self.status = "poll_error"
                self._push_sse("live_game_update", {"status": "poll_error", "error": str(e), "blue_win_probability": None})
                consecutive_failures += 1
                wait = exponential_backoff(consecutive_failures - 1, base_wait=POLL_INTERVAL, max_wait=MAX_POLL_INTERVAL)
            self._stop_event.wait(wait)

    def _poll(self) -> None:
        import numpy as np
        import pandas as pd
        import xgboost as xgb
        from lol_genius.model.train import load_model

        data = fetch_live_game_data(self.host, self.port)
        if not data:
            return

        game_id = data.get("gameData", {}).get("gameId")
        game_id_reset = game_id is not None and self._game_id is not None and game_id != self._game_id
        if game_id is not None:
            self._game_id = game_id

        all_players = data.get("allPlayers", [])
        if self._pregame_summary is None and all_players:
            self._enrich_pregame(all_players)

        game_state = parse_live_client_data(data)
        current_game_time = game_state.get("game_time", 0)
        time_reset = self._last_game_time is not None and current_game_time < self._last_game_time - 30
        game_reset = game_id_reset or time_reset
        self._last_game_time = current_game_time
        features = build_live_features(game_state, self._pregame_win_prob, self._pregame_summary)

        try:
            model, feature_names = load_model(self.model_dir, "live")
        except Exception as e:
            log.warning("Live model not found: %s", e)
            self._push_sse("live_game_update", {"status": "model_missing", "blue_win_probability": None})
            with self._lock:
                self.status = "model_missing"
            raise

        feat_df = pd.DataFrame([features])
        missing = [col for col in feature_names if col not in feat_df.columns]
        if missing:
            log.warning("Missing %d features (filling with 0.0): %s", len(missing), missing[:5])
            for col in missing:
                feat_df[col] = 0.0
        feat_df = feat_df[feature_names]

        dmat = xgb.DMatrix(feat_df, feature_names=feature_names)
        prob = float(model.predict(dmat)[0])

        from lol_genius.model.train import load_calibrator
        cal = load_calibrator(self.model_dir, "live")
        if cal is None:
            log.warning("No live calibrator found — predictions are uncalibrated")
        else:
            prob = float(np.interp(prob, cal["x_thresholds"], cal["y_thresholds"]))

        update = {
            "status": "ok",
            "game_time": game_state.get("game_time", 0),
            "blue_win_probability": prob,
            "kill_diff": game_state.get("kill_diff", 0),
            "dragon_diff": game_state.get("dragon_diff", 0),
            "tower_diff": game_state.get("tower_diff", 0),
            "baron_diff": game_state.get("baron_diff", 0),
            "cs_diff": game_state.get("cs_diff", 0),
            "inhibitor_diff": game_state.get("inhibitor_diff", 0),
            "elder_diff": game_state.get("elder_diff", 0),
            "game_reset": game_reset,
        }
        with self._lock:
            self.status = "ok"
            self.current = update
            if game_reset:
                self.history = []
            self.history.append({"game_time": update["game_time"], "probability": round(prob * 100, 1)})
            if len(self.history) > 100:
                self.history = self.history[-100:]
        self._push_sse("live_game_update", update)
