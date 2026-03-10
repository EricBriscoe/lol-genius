from __future__ import annotations

import json
import logging
import math
import threading
from pathlib import Path

from lol_genius.utils import exponential_backoff

log = logging.getLogger(__name__)

_SHARED_DIR = Path(__file__).resolve().parents[2] / "shared"

with open(_SHARED_DIR / "shap-categories.json") as _f:
    _SHAP_JSON = json.load(_f)


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


_POSITION_ABBREV = {
    "TOP": "top",
    "JUNGLE": "jg",
    "MIDDLE": "mid",
    "BOTTOM": "bot",
    "UTILITY": "sup",
}


def parse_live_client_data(data: dict) -> dict:
    all_players = data.get("allPlayers", [])
    events = data.get("events", {}).get("Events", [])
    game_time = data.get("gameData", {}).get("gameTime", 0.0)

    blue_kills = red_kills = 0
    blue_cs = red_cs = 0
    blue_levels: list[int] = []
    red_levels: list[int] = []
    per_role: dict[str, int | float] = {}

    for player in all_players:
        team = player.get("team", "")
        scores = player.get("scores", {})
        kills = scores.get("kills", 0)
        cs = scores.get("creepScore", scores.get("cs", 0))
        level = player.get("level", 1)
        pos_raw = player.get("position", "")
        pos = _POSITION_ABBREV.get(pos_raw)
        side = "blue" if team == "ORDER" else "red"
        if team == "ORDER":
            blue_kills += kills
            blue_cs += cs
            blue_levels.append(level)
        else:
            red_kills += kills
            red_cs += cs
            red_levels.append(level)
        if pos:
            per_role[f"{side}_{pos}_cs"] = cs
            per_role[f"{side}_{pos}_level"] = level
            per_role[f"{side}_{pos}_kills"] = kills

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
        "blue_avg_level": sum(blue_levels) / len(blue_levels) if blue_levels else 1.0,
        "red_avg_level": sum(red_levels) / len(red_levels) if red_levels else 1.0,
        "blue_max_level": max(blue_levels) if blue_levels else 1,
        "red_max_level": max(red_levels) if red_levels else 1,
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
        **per_role,
    }


def _snap_to_snapshot(game_time: float) -> int:
    from lol_genius.features.timeline import SNAPSHOT_SECONDS

    return min(SNAPSHOT_SECONDS, key=lambda t: abs(t - game_time))


def build_live_features(
    game_state: dict,
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
    raw_game_time = game_state.get("game_time", 0)
    kill_diff = game_state.get("kill_diff", 0)
    cs_diff = game_state.get("cs_diff", 0)
    tower_diff = game_state.get("tower_diff", 0)
    dragon_diff = game_state.get("dragon_diff", 0)

    prev = prev_diffs or {}
    raw_game_minutes = max(raw_game_time / 60.0, 1.0)

    blue_dragons = game_state.get("blue_dragons", 0)
    red_dragons = game_state.get("red_dragons", 0)
    blue_barons = game_state.get("blue_barons", 0)
    red_barons = game_state.get("red_barons", 0)
    blue_heralds = game_state.get("blue_heralds", 0)
    red_heralds = game_state.get("red_heralds", 0)

    abs_kill_diff = abs(kill_diff)
    abs_tower_diff = abs(tower_diff)

    total_objectives = (
        blue_dragons + red_dragons + blue_barons + red_barons + blue_heralds + red_heralds
    )

    mapping = {
        "game_time_seconds": raw_game_time,
        "blue_kills": game_state.get("blue_kills", 0),
        "red_kills": game_state.get("red_kills", 0),
        "kill_diff": kill_diff,
        "blue_cs": game_state.get("blue_cs", 0),
        "red_cs": game_state.get("red_cs", 0),
        "blue_towers": game_state.get("blue_towers", 0),
        "red_towers": game_state.get("red_towers", 0),
        "tower_diff": tower_diff,
        "blue_dragons": blue_dragons,
        "red_dragons": red_dragons,
        "dragon_diff": dragon_diff,
        "blue_barons": blue_barons,
        "red_barons": red_barons,
        "blue_heralds": blue_heralds,
        "red_heralds": red_heralds,
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
        "scaling_score_diff": summary.get("scaling_score_diff", 0.0),
        "stat_growth_diff": summary.get("stat_growth_diff", 0.0),
        "infinite_scaler_count_diff": summary.get("infinite_scaler_count_diff", 0.0),
        "kill_diff_delta": kill_diff - prev.get("kill_diff", kill_diff),
        "cs_diff_delta": cs_diff - prev.get("cs_diff", cs_diff),
        "tower_diff_delta": tower_diff - prev.get("tower_diff", tower_diff),
        "kill_lead_erosion": max(peak_kill_diff, abs_kill_diff) - abs_kill_diff,
        "tower_lead_erosion": max(peak_tower_diff, abs_tower_diff) - abs_tower_diff,
        "kill_rate_diff": kill_diff / raw_game_minutes,
        "cs_rate_diff": cs_diff / raw_game_minutes,
        "dragon_rate_diff": dragon_diff / raw_game_minutes,
        "kill_diff_accel": kill_diff_accel,
        "recent_kill_share_diff": recent_kill_share_diff,
        "objective_density": total_objectives / raw_game_minutes,
        "avg_level_diff": game_state.get("blue_avg_level", 1.0)
        - game_state.get("red_avg_level", 1.0),
        "max_level_diff": game_state.get("blue_max_level", 1) - game_state.get("red_max_level", 1),
        "blue_has_soul": 1.0 if blue_dragons >= 4 else 0.0,
        "red_has_soul": 1.0 if red_dragons >= 4 else 0.0,
        "blue_soul_point": 1.0 if blue_dragons >= 3 else 0.0,
        "red_soul_point": 1.0 if red_dragons >= 3 else 0.0,
    }

    for pos in ("top", "jg", "mid", "bot", "sup"):
        mapping[f"{pos}_cs_diff"] = float(
            game_state.get(f"blue_{pos}_cs", 0) - game_state.get(f"red_{pos}_cs", 0)
        )
        mapping[f"{pos}_level_diff"] = float(
            game_state.get(f"blue_{pos}_level", 1) - game_state.get(f"red_{pos}_level", 1)
        )
        mapping[f"{pos}_kill_diff"] = float(
            game_state.get(f"blue_{pos}_kills", 0) - game_state.get(f"red_{pos}_kills", 0)
        )

    return {col: mapping.get(col, 0) for col in LIVE_FEATURE_NAMES}


POLL_INTERVAL = 15
MAX_POLL_INTERVAL = 300
NO_DATA_THRESHOLD = 3

_LIVE_CATEGORY_MAP = _SHAP_JSON["live_category_map"]

_EXCLUDED_FEATURES = set(_SHAP_JSON["excluded_features"])

_LIVE_FEATURE_TO_CAT = {feat: cat for cat, feats in _LIVE_CATEGORY_MAP.items() for feat in feats}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


_IMPACT_THRESHOLD = _SHAP_JSON["impact_threshold"]
_MAX_GROUPS = _SHAP_JSON["max_groups"]
_NARR = _SHAP_JSON["narrative_config"]


def _build_factor_analysis(base_value: float, shap_dict: dict[str, float]) -> dict:
    total_shap = sum(shap_dict.values())
    total_log_odds = base_value + total_shap
    total_prob = _sigmoid(total_log_odds)

    cat_shap: dict[str, float] = {}
    for feature, shap_val in shap_dict.items():
        if feature in _EXCLUDED_FEATURES:
            continue
        cat = _LIVE_FEATURE_TO_CAT.get(feature)
        if cat:
            cat_shap[cat] = cat_shap.get(cat, 0.0) + shap_val

    groups = []
    for category, group_shap in cat_shap.items():
        without = total_log_odds - group_shap
        prob_without = _sigmoid(without)
        impact_pct = round((total_prob - prob_without) * 100, 1)
        if abs(impact_pct) >= _IMPACT_THRESHOLD:
            groups.append({"category": category, "impactPct": impact_pct})

    groups.sort(key=lambda g: abs(g["impactPct"]), reverse=True)
    groups = groups[:_MAX_GROUPS]

    pregame_shap = shap_dict.get("pregame_blue_win_prob", 0)
    displayed_total = sum(abs(g["impactPct"]) for g in groups)

    if not groups and abs(pregame_shap) > 0.1:
        narrative = "Prediction largely driven by pregame draft and skill analysis."
    elif not groups:
        narrative = "An evenly matched game with no dominant factors."
    else:
        top = groups[0]
        direction = "Blue" if top["impactPct"] > 0 else "Red"
        magnitude = abs(top["impactPct"])
        if magnitude >= _NARR["strong_threshold"]:
            strength = "strong"
        elif magnitude >= _NARR["moderate_threshold"]:
            strength = "moderate"
        else:
            strength = "slight"
        narrative = f"{direction} favored by a {strength} {top['category'].lower()} edge"
        if len(groups) > 1 and abs(groups[1]["impactPct"]) >= _NARR["second_factor_threshold"]:
            second_dir = "blue" if groups[1]["impactPct"] > 0 else "red"
            verb = "supported" if second_dir == direction.lower() else "offset"
            narrative += f", {verb} by {groups[1]['category'].lower()}"
        if displayed_total < abs(pregame_shap) * _NARR["pregame_dominance_multiplier"]:
            narrative += " — largely driven by pregame analysis"
        narrative += "."

    return {"groups": groups, "narrative": narrative}


class LiveGamePoller:
    def __init__(
        self,
        host: str,
        port: int,
        model_dir: str,
        push_sse_fn,
        dsn: str | None = None,
        proxy_url: str | None = None,
        ddragon_cache: str | None = None,
    ):
        self.host = host
        self.port = port
        self.model_dir = model_dir
        self._push_sse = push_sse_fn
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
        self._last_snapshot: int | None = None
        self._prev_recent_kill_share_diff: float = 0.0
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
            }

    def _enrich_pregame(self, all_players: list[dict]) -> None:
        if not (self._dsn and self._proxy_url and self._ddragon_cache):
            log.warning("Pregame enrichment skipped: missing dsn, proxy_url, or ddragon_cache")
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
                compute_pregame_diff_from_group,
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
                            "champion_name": p.get("championName", p.get("rawChampionName", "")),
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
                mastery_by_key = {(m["puuid"], m["champion_id"]): m for m in masteries_list}

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
                            "mastery_points": (mastery_data or {}).get("mastery_points", 0),
                            "mastery_level": (mastery_data or {}).get("mastery_level", 0),
                        }
                    )

                group = pd.DataFrame(rows)
                summary = compute_pregame_diff_from_group(
                    group,
                    ddragon,
                    champ_wrs,
                    scaling_scores,
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
                                    f"No response from Live Client API at {self.host}:{self.port}"
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
            game_id is not None and self._game_id is not None and game_id != self._game_id
        )
        if game_id is not None:
            self._game_id = game_id

        all_players = data.get("allPlayers", [])
        with self._lock:
            should_enrich = self._pregame_summary is None and all_players and not self._enriching
            if should_enrich:
                self._enriching = True
        if should_enrich:
            threading.Thread(target=self._enrich_pregame, args=(all_players,), daemon=True).start()

        game_state = parse_live_client_data(data)
        current_game_time = game_state.get("game_time", 0)
        time_reset = (
            self._last_game_time is not None and current_game_time < self._last_game_time - 30
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
            self._last_snapshot = None
            self._prev_recent_kill_share_diff = 0.0
            self._pregame_summary = None
            self._enriching = False

        kill_diff = game_state.get("kill_diff", 0)
        tower_diff = game_state.get("tower_diff", 0)
        blue_kills = game_state.get("blue_kills", 0)
        red_kills = game_state.get("red_kills", 0)

        current_snapshot = _snap_to_snapshot(current_game_time)
        snapshot_changed = self._last_snapshot is None or current_snapshot != self._last_snapshot

        if snapshot_changed and self._prev_diffs is not None:
            kill_diff_delta = kill_diff - self._prev_diffs.get("kill_diff", kill_diff)
            blue_recent = blue_kills - self._prev_blue_kills
            red_recent = red_kills - self._prev_red_kills
            recent_kill_share_diff = blue_recent / max(blue_kills, 1) - red_recent / max(
                red_kills, 1
            )
            self._prev_recent_kill_share_diff = recent_kill_share_diff
        elif self._prev_diffs is not None:
            kill_diff_delta = self._prev_kill_diff_delta
            recent_kill_share_diff = self._prev_recent_kill_share_diff
        else:
            kill_diff_delta = 0.0
            recent_kill_share_diff = 0.0

        kill_diff_accel = kill_diff_delta - self._prev_kill_diff_delta
        abs_kill_diff = abs(kill_diff)
        abs_tower_diff = abs(tower_diff)
        if self._peak_kill_diff is None:
            peak_kill_diff = abs_kill_diff
        else:
            peak_kill_diff = max(self._peak_kill_diff, abs_kill_diff)
        if self._peak_tower_diff is None:
            peak_tower_diff = abs_tower_diff
        else:
            peak_tower_diff = max(self._peak_tower_diff, abs_tower_diff)

        with self._lock:
            pregame_summary = self._pregame_summary
        features = build_live_features(
            game_state,
            pregame_summary,
            prev_diffs=self._prev_diffs,
            peak_kill_diff=peak_kill_diff,
            peak_tower_diff=peak_tower_diff,
            kill_diff_accel=kill_diff_accel,
            recent_kill_share_diff=recent_kill_share_diff,
        )
        if snapshot_changed:
            self._prev_diffs = {
                "kill_diff": kill_diff,
                "cs_diff": game_state.get("cs_diff", 0),
                "tower_diff": tower_diff,
            }
            self._prev_kill_diff_delta = kill_diff_delta
            self._prev_blue_kills = blue_kills
            self._prev_red_kills = red_kills
            self._last_snapshot = current_snapshot
        self._peak_kill_diff = peak_kill_diff
        self._peak_tower_diff = peak_tower_diff

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
            if len(missing) > len(feature_names) // 2:
                log.error(
                    "More than half of features missing (%d/%d): %s",
                    len(missing),
                    len(feature_names),
                    missing[:10],
                )
            else:
                log.warning("Missing %d features: %s", len(missing), missing[:5])
            for col in missing:
                feat_df[col] = 0.0
        feat_df = feat_df[feature_names]

        dmat = xgb.DMatrix(feat_df, feature_names=feature_names)
        prob = float(model.predict(dmat)[0])

        from lol_genius.model.train import load_calibrator

        cal = load_calibrator(self.model_dir, "live")
        if cal is None:
            log.warning("No live calibrator found — predictions are uncalibrated")
        elif cal.get("method") == "platt":
            a, b = cal["a"], cal["b"]
            prob = float(1.0 / (1.0 + np.exp(-(a * prob + b))))
        else:
            prob = float(np.interp(prob, cal["x_thresholds"], cal["y_thresholds"]))

        try:
            explainer = self._get_explainer(model)
            shap_values = explainer.shap_values(feat_df)
            sv = shap_values[0] if len(shap_values.shape) > 1 else shap_values
            base_value = float(np.asarray(explainer.expected_value).flat[0])
            shap_dict = dict(zip(feature_names, (float(v) for v in sv)))
            factor_analysis = _build_factor_analysis(base_value, shap_dict)
        except Exception:
            log.debug("SHAP computation failed", exc_info=True)
            factor_analysis = {"groups": [], "narrative": ""}

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
            "factor_analysis": factor_analysis,
            "pregame_ready": pregame_summary is not None,
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
