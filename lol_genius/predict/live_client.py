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
    *,
    prev_diffs: dict | None = None,
    peak_kill_diff: float = 0.0,
    peak_tower_diff: float = 0.0,
    kill_diff_accel: float = 0.0,
    recent_kill_share_diff: float = 0.0,
) -> dict:
    from lol_genius.features.timeline import LIVE_FEATURE_NAMES

    summary = pregame_summary or {}
    game_time = _snap_to_snapshot(game_state.get("game_time", 0))
    kill_diff = game_state.get("kill_diff", 0)
    cs_diff = game_state.get("cs_diff", 0)
    tower_diff = game_state.get("tower_diff", 0)
    dragon_diff = game_state.get("dragon_diff", 0)

    prev = prev_diffs or {}
    scaling_score_diff = summary.get("scaling_score_diff", 0.0)
    game_minutes = max(game_time / 60.0, 1.0)

    mapping = {
        "game_time_seconds": game_time,
        "blue_kills": game_state.get("blue_kills", 0),
        "red_kills": game_state.get("red_kills", 0),
        "kill_diff": kill_diff,
        "blue_cs": game_state.get("blue_cs", 0),
        "red_cs": game_state.get("red_cs", 0),
        "blue_towers": game_state.get("blue_towers", 0),
        "red_towers": game_state.get("red_towers", 0),
        "tower_diff": tower_diff,
        "blue_dragons": game_state.get("blue_dragons", 0),
        "red_dragons": game_state.get("red_dragons", 0),
        "dragon_diff": dragon_diff,
        "blue_barons": game_state.get("blue_barons", 0),
        "red_barons": game_state.get("red_barons", 0),
        "blue_heralds": game_state.get("blue_heralds", 0),
        "red_heralds": game_state.get("red_heralds", 0),
        "blue_inhibitors": game_state.get("blue_inhibitors", 0),
        "red_inhibitors": game_state.get("red_inhibitors", 0),
        "blue_elder": game_state.get("blue_elder", 0),
        "red_elder": game_state.get("red_elder", 0),
        "cs_diff": cs_diff,
        "inhibitor_diff": game_state.get("inhibitor_diff", 0),
        "elder_diff": game_state.get("elder_diff", 0),
        "first_blood_blue": game_state.get("first_blood_blue", 0),
        "first_tower_blue": game_state.get("first_tower_blue", 0),
        "first_dragon_blue": game_state.get("first_dragon_blue", 0),
        "pregame_blue_win_prob": pregame_win_prob
        if pregame_win_prob is not None
        else 0.5,
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
        "scaling_score_diff": scaling_score_diff,
        "max_scaling_score_diff": summary.get("max_scaling_score_diff", 0.0),
        "stat_growth_diff": summary.get("stat_growth_diff", 0.0),
        "scaling_advantage_realized": scaling_score_diff * (game_time / 1800.0),
        "early_game_window_closing": scaling_score_diff
        * max(0.0, 1.0 - game_time / 1500.0),
        "kill_diff_delta": kill_diff - prev.get("kill_diff", kill_diff),
        "cs_diff_delta": cs_diff - prev.get("cs_diff", cs_diff),
        "tower_diff_delta": tower_diff - prev.get("tower_diff", tower_diff),
        "kill_lead_erosion": max(peak_kill_diff, kill_diff) - kill_diff,
        "tower_lead_erosion": max(peak_tower_diff, tower_diff) - tower_diff,
        "kill_rate_diff": kill_diff / game_minutes,
        "cs_rate_diff": cs_diff / game_minutes,
        "dragon_rate_diff": dragon_diff / game_minutes,
        "kill_diff_accel": kill_diff_accel,
        "recent_kill_share_diff": recent_kill_share_diff,
    }
    return {col: mapping.get(col, 0) for col in LIVE_FEATURE_NAMES}


POLL_INTERVAL = 15
MAX_POLL_INTERVAL = 300
NO_DATA_THRESHOLD = 3


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
        self._prev_diffs: dict | None = None
        self._peak_kill_diff: float | None = None
        self._peak_tower_diff: float | None = None
        self._prev_kill_diff_delta: float = 0.0
        self._prev_blue_kills: int = 0
        self._prev_red_kills: int = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.current: dict | None = None
        self.history: list[dict] = []
        self.status: str = "waiting"
        self._game_id: int | None = None
        self._last_game_time: float | None = None
        self._enriching = False
        self._explainer: object | None = None
        self._explainer_model_id: int | None = None

    def _get_explainer(self, model):
        import shap

        model_id = id(model)
        if self._explainer is None or self._explainer_model_id != model_id:
            self._explainer = shap.TreeExplainer(model)
            self._explainer_model_id = model_id
        return self._explainer

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
            log.warning(
                "Pregame enrichment skipped: missing dsn, proxy_url, or ddragon_cache"
            )
            with self._lock:
                self._pregame_summary = {}
                self._enriching = False
            return

        try:
            import pandas as pd

            from lol_genius.api.ddragon import DataDragon
            from lol_genius.api.proxy_client import ProxyClient
            from lol_genius.db.queries import MatchDB
            from lol_genius.features.timeline import (
                _extract_team_vectors,
                compute_pregame_diff_stats,
            )

            ddragon = DataDragon(self._ddragon_cache)
            proxy = ProxyClient(self._proxy_url, priority="high")
            db = MatchDB(self._dsn)

            try:
                champ_wrs = db.get_champion_patch_winrates()
                scaling_scores = db.get_champion_scaling_scores()

                player_info = []
                for p in all_players:
                    riot_id = p.get("riotId", "")
                    parts = riot_id.rsplit("#", 1)
                    game_name = parts[0] if parts else riot_id
                    tag_line = parts[1] if len(parts) == 2 else ""
                    player_info.append(
                        {
                            "key": riot_id,
                            "game_name": game_name,
                            "tag_line": tag_line,
                            "champion_name": p.get(
                                "championName", p.get("rawChampionName", "")
                            ),
                            "team": p.get("team", "ORDER"),
                        }
                    )

                puuid_map = {}
                for p in player_info:
                    result = proxy.get_account_by_riot_id(p["game_name"], p["tag_line"])
                    if result and result.get("puuid"):
                        puuid_map[p["key"]] = result["puuid"]

                if not puuid_map:
                    log.warning("Pregame enrichment: could not resolve any PUUIDs")
                    with self._lock:
                        self._pregame_summary = {}
                        self._enriching = False
                    return

                ranks_list, masteries_list = db.get_ranks_and_mastery_by_puuids(
                    list(puuid_map.values())
                )
                rank_by_puuid = {r["puuid"]: r for r in ranks_list}
                mastery_by_key = {
                    (m["puuid"], m["champion_id"]): m for m in masteries_list
                }

                rows = []
                for p in player_info:
                    puuid = puuid_map.get(p["key"])
                    champ_id = ddragon.get_champion_id_by_name(p["champion_name"])
                    rank_data = rank_by_puuid.get(puuid) if puuid else None
                    mastery_data = (
                        mastery_by_key.get((puuid, champ_id))
                        if (puuid and champ_id is not None)
                        else None
                    )
                    rows.append(
                        {
                            "team_id": 100 if p["team"] == "ORDER" else 200,
                            "champion_id": champ_id,
                            "tier": (rank_data or {}).get("tier"),
                            "rank": (rank_data or {}).get("rank"),
                            "league_points": (rank_data or {}).get("league_points", 0),
                            "wins": (rank_data or {}).get("wins", 0),
                            "losses": (rank_data or {}).get("losses", 0),
                            "hot_streak": (rank_data or {}).get("hot_streak", 0),
                            "veteran": (rank_data or {}).get("veteran", 0),
                            "mastery_points": (mastery_data or {}).get(
                                "mastery_points", 0
                            ),
                            "mastery_level": (mastery_data or {}).get(
                                "mastery_level", 0
                            ),
                        }
                    )

                group = pd.DataFrame(rows)
                vectors = _extract_team_vectors(
                    group,
                    ddragon,
                    champ_wrs,
                    scaling_scores,
                    ddragon.stat_growth_score,
                )
                (
                    b_ranks,
                    r_ranks,
                    b_wrs,
                    r_wrs,
                    b_mast,
                    r_mast,
                    b_melee,
                    r_melee,
                    b_ad,
                    r_ad,
                    b_tg,
                    r_tg,
                    b_hs,
                    r_hs,
                    b_vet,
                    r_vet,
                    b_m7,
                    r_m7,
                    b_cwr,
                    r_cwr,
                    b_ss,
                    r_ss,
                    b_sg,
                    r_sg,
                ) = vectors
                summary = compute_pregame_diff_stats(
                    b_ranks,
                    r_ranks,
                    b_wrs,
                    r_wrs,
                    b_mast,
                    r_mast,
                    b_melee,
                    r_melee,
                    b_ad,
                    r_ad,
                    blue_total_games=b_tg,
                    red_total_games=r_tg,
                    blue_hot_streaks=b_hs,
                    red_hot_streaks=r_hs,
                    blue_veterans=b_vet,
                    red_veterans=r_vet,
                    blue_mastery7=b_m7,
                    red_mastery7=r_m7,
                    blue_champ_wrs=b_cwr,
                    red_champ_wrs=r_cwr,
                    blue_scaling_scores=b_ss,
                    red_scaling_scores=r_ss,
                    blue_stat_growth=b_sg,
                    red_stat_growth=r_sg,
                )
                with self._lock:
                    self._pregame_summary = summary
                    self._enriching = False
                log.info("Enriched pregame features for game %s", self._game_id)
            finally:
                proxy.close()
                db.close()

        except Exception:
            log.warning("Pregame enrichment failed, using defaults", exc_info=True)
            with self._lock:
                self._pregame_summary = {}
                self._enriching = False

    def _poll_loop(self) -> None:
        consecutive_failures = 0
        consecutive_no_data = 0
        while not self._stop_event.is_set():
            try:
                got_data = self._poll()
                consecutive_failures = 0
                if got_data:
                    consecutive_no_data = 0
                else:
                    consecutive_no_data += 1
                    if consecutive_no_data == NO_DATA_THRESHOLD:
                        with self._lock:
                            self.status = "no_data"
                        self._push_sse(
                            "live_game_update",
                            {
                                "status": "no_data",
                                "error": (
                                    "No response from Live Client API"
                                    f" at {self.host}:{self.port}"
                                ),
                                "blue_win_probability": None,
                            },
                        )
                wait = POLL_INTERVAL
            except Exception as e:
                log.warning(f"Live game poll error: {e}")
                with self._lock:
                    self.status = "poll_error"
                self._push_sse(
                    "live_game_update",
                    {
                        "status": "poll_error",
                        "error": str(e),
                        "blue_win_probability": None,
                    },
                )
                consecutive_failures += 1
                wait = exponential_backoff(
                    consecutive_failures - 1,
                    base_wait=POLL_INTERVAL,
                    max_wait=MAX_POLL_INTERVAL,
                )
            self._stop_event.wait(wait)

    def _poll(self) -> bool:
        import numpy as np
        import pandas as pd
        import xgboost as xgb

        from lol_genius.model.train import load_model

        data = fetch_live_game_data(self.host, self.port)
        if not data:
            return False

        game_id = data.get("gameData", {}).get("gameId")
        game_id_reset = (
            game_id is not None
            and self._game_id is not None
            and game_id != self._game_id
        )
        if game_id is not None:
            self._game_id = game_id

        all_players = data.get("allPlayers", [])
        with self._lock:
            should_enrich = (
                self._pregame_summary is None and all_players and not self._enriching
            )
            if should_enrich:
                self._enriching = True
        if should_enrich:
            threading.Thread(
                target=self._enrich_pregame, args=(all_players,), daemon=True
            ).start()

        game_state = parse_live_client_data(data)
        current_game_time = game_state.get("game_time", 0)
        time_reset = (
            self._last_game_time is not None
            and current_game_time < self._last_game_time - 30
        )
        game_reset = game_id_reset or time_reset
        self._last_game_time = current_game_time
        if game_reset:
            self._prev_diffs = None
            self._peak_kill_diff = None
            self._peak_tower_diff = None
            self._prev_kill_diff_delta = 0.0
            self._prev_blue_kills = 0
            self._prev_red_kills = 0
            self._pregame_summary = None
            self._enriching = False

        kill_diff = game_state.get("kill_diff", 0)
        tower_diff = game_state.get("tower_diff", 0)
        blue_kills = game_state.get("blue_kills", 0)
        red_kills = game_state.get("red_kills", 0)

        if self._prev_diffs is not None:
            kill_diff_delta = kill_diff - self._prev_diffs.get("kill_diff", kill_diff)
            blue_recent = blue_kills - self._prev_blue_kills
            red_recent = red_kills - self._prev_red_kills
            recent_kill_share_diff = blue_recent / max(
                blue_kills, 1
            ) - red_recent / max(red_kills, 1)
        else:
            kill_diff_delta = 0.0
            recent_kill_share_diff = 0.0

        kill_diff_accel = kill_diff_delta - self._prev_kill_diff_delta
        if self._peak_kill_diff is None:
            peak_kill_diff = kill_diff
        else:
            peak_kill_diff = max(self._peak_kill_diff, kill_diff)
        if self._peak_tower_diff is None:
            peak_tower_diff = tower_diff
        else:
            peak_tower_diff = max(self._peak_tower_diff, tower_diff)

        with self._lock:
            pregame_summary = self._pregame_summary
        features = build_live_features(
            game_state,
            self._pregame_win_prob,
            pregame_summary,
            prev_diffs=self._prev_diffs,
            peak_kill_diff=peak_kill_diff,
            peak_tower_diff=peak_tower_diff,
            kill_diff_accel=kill_diff_accel,
            recent_kill_share_diff=recent_kill_share_diff,
        )
        self._prev_diffs = {
            "kill_diff": kill_diff,
            "cs_diff": game_state.get("cs_diff", 0),
            "tower_diff": tower_diff,
        }
        self._peak_kill_diff = peak_kill_diff
        self._peak_tower_diff = peak_tower_diff
        self._prev_kill_diff_delta = kill_diff_delta
        self._prev_blue_kills = blue_kills
        self._prev_red_kills = red_kills

        try:
            model, feature_names = load_model(self.model_dir, "live")
        except Exception as e:
            log.warning("Live model not found: %s", e)
            self._push_sse(
                "live_game_update",
                {"status": "model_missing", "blue_win_probability": None},
            )
            with self._lock:
                self.status = "model_missing"
            raise

        feat_df = pd.DataFrame([features])
        missing = [col for col in feature_names if col not in feat_df.columns]
        if missing:
            log.warning(
                "Missing %d features (filling with 0.0): %s", len(missing), missing[:5]
            )
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

        try:
            explainer = self._get_explainer(model)
            shap_values = explainer.shap_values(feat_df)
            sv = shap_values[0] if len(shap_values.shape) > 1 else shap_values
            top_factors = [
                {"feature": name, "impact": round(float(imp), 4)}
                for name, imp in sorted(
                    zip(feature_names, sv), key=lambda x: abs(x[1]), reverse=True
                )[:8]
            ]
        except Exception:
            log.debug("SHAP computation failed", exc_info=True)
            top_factors = []

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
            "top_factors": top_factors,
        }
        with self._lock:
            self.status = "ok"
            self.current = update
            if game_reset:
                self.history = []
            self.history.append(
                {"game_time": update["game_time"], "probability": round(prob * 100, 1)}
            )
            if len(self.history) > 100:
                self.history = self.history[-100:]
        self._push_sse("live_game_update", update)
        return True
