from __future__ import annotations

import logging

from datetime import datetime, timedelta, timezone

from lol_genius.features.stats import aggregate_recent_stats

from .connection import get_connection, get_connection_fast

log = logging.getLogger(__name__)


class MatchDB:
    def __init__(self, dsn: str, fast: bool = False):
        self.dsn = dsn
        self.conn = get_connection_fast(dsn) if fast else get_connection(dsn)
        self._batch_mode = False

    def _execute(self, sql, params=None):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur

    def close(self):
        self.conn.close()

    def begin_batch(self):
        self._batch_mode = True

    def flush(self):
        self.conn.commit()

    def end_batch(self):
        self.conn.commit()
        self._batch_mode = False

    def _maybe_commit(self):
        if not self._batch_mode:
            self.conn.commit()

    def recover_stuck_processing(self) -> int:
        cursor = self._execute(
            "UPDATE crawl_queue SET status = 'pending' WHERE status = 'processing'"
        )
        self._maybe_commit()
        return max(0, cursor.rowcount)

    def match_exists(self, match_id: str) -> bool:
        row = self._execute("SELECT 1 FROM matches WHERE match_id = %s", (match_id,)).fetchone()
        return row is not None

    def insert_match(
        self,
        match: dict,
        participants: list[dict],
        bans: list[dict] | None = None,
        objectives: list[dict] | None = None,
        raw_json: str | None = None,
    ) -> None:
        self._execute(
            """INSERT INTO matches
               (match_id, game_version, patch, game_duration, queue_id, blue_win, game_creation,
                game_start_timestamp, game_end_timestamp, platform_id)
               VALUES (%(match_id)s, %(game_version)s, %(patch)s, %(game_duration)s, %(queue_id)s, %(blue_win)s, %(game_creation)s,
                       %(game_start_timestamp)s, %(game_end_timestamp)s, %(platform_id)s)
               ON CONFLICT (match_id) DO NOTHING""",
            match,
        )
        for p in participants:
            self._execute(
                """INSERT INTO participants
                   (match_id, puuid, summoner_id, team_id, champion_id, champion_name, team_position, win,
                    kills, deaths, assists, total_damage, cs, vision_score, gold_earned,
                    summoner1_id, summoner2_id, summoner_level,
                    perks_primary_style, perks_sub_style, perks_keystone, perks_offense, perks_flex, perks_defense,
                    magic_damage_to_champions, physical_damage_to_champions, true_damage_to_champions,
                    total_damage_taken, damage_self_mitigated,
                    wards_placed, wards_killed, detector_wards_placed,
                    gold_spent, time_ccing_others, total_heal, total_heals_on_teammates,
                    double_kills, triple_kills, quadra_kills, penta_kills, largest_killing_spree,
                    item0, item1, item2, item3, item4, item5, item6,
                    neutral_minions_killed, total_minions_killed, champion_level)
                   VALUES (%(match_id)s, %(puuid)s, %(summoner_id)s, %(team_id)s, %(champion_id)s, %(champion_name)s,
                           %(team_position)s, %(win)s, %(kills)s, %(deaths)s, %(assists)s, %(total_damage)s, %(cs)s,
                           %(vision_score)s, %(gold_earned)s,
                           %(summoner1_id)s, %(summoner2_id)s, %(summoner_level)s,
                           %(perks_primary_style)s, %(perks_sub_style)s, %(perks_keystone)s, %(perks_offense)s, %(perks_flex)s, %(perks_defense)s,
                           %(magic_damage_to_champions)s, %(physical_damage_to_champions)s, %(true_damage_to_champions)s,
                           %(total_damage_taken)s, %(damage_self_mitigated)s,
                           %(wards_placed)s, %(wards_killed)s, %(detector_wards_placed)s,
                           %(gold_spent)s, %(time_ccing_others)s, %(total_heal)s, %(total_heals_on_teammates)s,
                           %(double_kills)s, %(triple_kills)s, %(quadra_kills)s, %(penta_kills)s, %(largest_killing_spree)s,
                           %(item0)s, %(item1)s, %(item2)s, %(item3)s, %(item4)s, %(item5)s, %(item6)s,
                           %(neutral_minions_killed)s, %(total_minions_killed)s, %(champion_level)s)
                   ON CONFLICT (match_id, puuid) DO NOTHING""",
                p,
            )

        if bans:
            for b in bans:
                self._execute(
                    """INSERT INTO match_bans (match_id, team_id, champion_id, pick_turn)
                       VALUES (%(match_id)s, %(team_id)s, %(champion_id)s, %(pick_turn)s)""",
                    b,
                )

        if objectives:
            for o in objectives:
                self._execute(
                    """INSERT INTO match_team_objectives (match_id, team_id, objective, first, kills)
                       VALUES (%(match_id)s, %(team_id)s, %(objective)s, %(first)s, %(kills)s)
                       ON CONFLICT (match_id, team_id, objective) DO NOTHING""",
                    o,
                )

        if raw_json:
            self._execute(
                "INSERT INTO match_raw_json (match_id, raw_json) VALUES (%s, %s::jsonb) ON CONFLICT (match_id) DO NOTHING",
                (match["match_id"], raw_json),
            )

        self._execute(
            "INSERT INTO match_enrichment_status (match_id, enriched) VALUES (%s, 0) ON CONFLICT (match_id) DO NOTHING",
            (match["match_id"],),
        )
        self._maybe_commit()

    def insert_summoner_rank(self, rank_data: dict) -> None:
        self._execute(
            """INSERT INTO summoner_ranks
               (puuid, summoner_id, queue_type, tier, rank, league_points, wins, losses,
                veteran, inactive, fresh_blood, hot_streak)
               VALUES (%(puuid)s, %(summoner_id)s, %(queue_type)s, %(tier)s, %(rank)s, %(league_points)s, %(wins)s, %(losses)s,
                       %(veteran)s, %(inactive)s, %(fresh_blood)s, %(hot_streak)s)
               ON CONFLICT (puuid, queue_type, fetched_at) DO UPDATE SET
                   tier = EXCLUDED.tier, rank = EXCLUDED.rank, league_points = EXCLUDED.league_points,
                   wins = EXCLUDED.wins, losses = EXCLUDED.losses,
                   veteran = EXCLUDED.veteran, inactive = EXCLUDED.inactive,
                   fresh_blood = EXCLUDED.fresh_blood, hot_streak = EXCLUDED.hot_streak""",
            rank_data,
        )
        self._maybe_commit()

    def upsert_player_recent_stats(self, stats: dict) -> None:
        self._execute(
            """INSERT INTO player_recent_stats
               (puuid, games_played, wins, avg_kills, avg_deaths, avg_assists,
                avg_cs_per_min, avg_vision, avg_damage_share,
                avg_wards_placed, avg_wards_killed, avg_damage_taken, avg_gold_spent,
                avg_cc_score, avg_heal_total, avg_magic_dmg_share, avg_phys_dmg_share, avg_multikill_rate)
               VALUES (%(puuid)s, %(games_played)s, %(wins)s, %(avg_kills)s, %(avg_deaths)s, %(avg_assists)s,
                        %(avg_cs_per_min)s, %(avg_vision)s, %(avg_damage_share)s,
                        %(avg_wards_placed)s, %(avg_wards_killed)s, %(avg_damage_taken)s, %(avg_gold_spent)s,
                        %(avg_cc_score)s, %(avg_heal_total)s, %(avg_magic_dmg_share)s, %(avg_phys_dmg_share)s, %(avg_multikill_rate)s)
               ON CONFLICT (puuid) DO UPDATE SET
                   games_played = EXCLUDED.games_played, wins = EXCLUDED.wins,
                   avg_kills = EXCLUDED.avg_kills, avg_deaths = EXCLUDED.avg_deaths, avg_assists = EXCLUDED.avg_assists,
                   avg_cs_per_min = EXCLUDED.avg_cs_per_min, avg_vision = EXCLUDED.avg_vision, avg_damage_share = EXCLUDED.avg_damage_share,
                   avg_wards_placed = EXCLUDED.avg_wards_placed, avg_wards_killed = EXCLUDED.avg_wards_killed,
                   avg_damage_taken = EXCLUDED.avg_damage_taken, avg_gold_spent = EXCLUDED.avg_gold_spent,
                   avg_cc_score = EXCLUDED.avg_cc_score, avg_heal_total = EXCLUDED.avg_heal_total,
                   avg_magic_dmg_share = EXCLUDED.avg_magic_dmg_share, avg_phys_dmg_share = EXCLUDED.avg_phys_dmg_share,
                   avg_multikill_rate = EXCLUDED.avg_multikill_rate,
                   computed_at = current_timestamp""",
            stats,
        )
        self._maybe_commit()

    def add_puuids_to_queue(self, puuids: list[str], tier: str = "UNKNOWN") -> int:
        added = 0
        for puuid in puuids:
            cur = self._execute(
                "INSERT INTO crawl_queue (puuid, seed_tier) VALUES (%s, %s) ON CONFLICT (puuid) DO NOTHING",
                (puuid, tier),
            )
            if cur.rowcount > 0:
                added += 1
        self._maybe_commit()
        return added

    def get_pending_puuids(self, limit: int = 100, tier_weights: dict[str, int] | None = None) -> list[str]:
        if tier_weights:
            ranked = sorted(tier_weights.items(), key=lambda x: x[1])
            tier_case = " ".join(f"WHEN '{t}' THEN {i + 1}" for i, (t, _) in enumerate(ranked))
        else:
            tiers = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "UNKNOWN"]
            tier_case = " ".join(f"WHEN '{t}' THEN {i + 1}" for i, t in enumerate(tiers))
        sql = f"""
            SELECT puuid FROM (
                SELECT puuid,
                    ROW_NUMBER() OVER (PARTITION BY seed_tier ORDER BY added_at) AS rn,
                    CASE seed_tier {tier_case} ELSE 99 END AS tier_order
                FROM crawl_queue WHERE status = 'pending'
            ) sub
            ORDER BY rn, tier_order
            LIMIT %s
        """
        rows = self._execute(sql, (limit,)).fetchall()
        return [r["puuid"] for r in rows]

    def mark_puuid_processing(self, puuid: str) -> None:
        self._execute(
            "UPDATE crawl_queue SET status = 'processing' WHERE puuid = %s", (puuid,)
        )
        self._maybe_commit()

    def mark_puuid_done(self, puuid: str) -> None:
        self._execute(
            "UPDATE crawl_queue SET status = 'done', processed_at = current_timestamp WHERE puuid = %s",
            (puuid,),
        )
        self._maybe_commit()

    def get_unenriched_matches(self, limit: int = 100) -> list[str]:
        rows = self._execute(
            "SELECT match_id FROM match_enrichment_status WHERE enriched = 0 LIMIT %s",
            (limit,),
        ).fetchall()
        return [r["match_id"] for r in rows]

    def mark_match_enriched(self, match_id: str) -> None:
        self._execute(
            "UPDATE match_enrichment_status SET enriched = 1, enriched_at = current_timestamp WHERE match_id = %s",
            (match_id,),
        )
        self._maybe_commit()

    def get_match_count(self) -> int:
        row = self._execute("SELECT COUNT(*) as cnt FROM matches").fetchone()
        return row["cnt"]

    def get_queue_stats(self) -> dict:
        rows = self._execute(
            "SELECT status, COUNT(*) as cnt FROM crawl_queue GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}

    def get_queue_stats_by_tier(self) -> dict[str, dict[str, int]]:
        rows = self._execute(
            "SELECT seed_tier, status, COUNT(*) as cnt FROM crawl_queue GROUP BY seed_tier, status"
        ).fetchall()
        result: dict[str, dict[str, int]] = {}
        for r in rows:
            tier = r["seed_tier"]
            if tier not in result:
                result[tier] = {}
            result[tier][r["status"]] = r["cnt"]
        return result

    def get_enrichment_stats(self) -> dict:
        row = self._execute(
            "SELECT SUM(enriched) as done, COUNT(*) as total FROM match_enrichment_status"
        ).fetchone()
        return {"enriched": row["done"] or 0, "total": row["total"] or 0}

    def get_participants_for_match(self, match_id: str) -> list[dict]:
        rows = self._execute(
            "SELECT * FROM participants WHERE match_id = %s", (match_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_match(self, match_id: str) -> dict | None:
        row = self._execute("SELECT * FROM matches WHERE match_id = %s", (match_id,)).fetchone()
        return dict(row) if row else None

    def get_latest_rank(self, puuid: str, queue_type: str = "RANKED_SOLO_5x5") -> dict | None:
        row = self._execute(
            "SELECT * FROM summoner_ranks WHERE puuid = %s AND queue_type = %s ORDER BY fetched_at DESC LIMIT 1",
            (puuid, queue_type),
        ).fetchone()
        return dict(row) if row else None

    def has_mastery_data(self, puuid: str) -> bool:
        row = self._execute(
            "SELECT 1 FROM champion_mastery WHERE puuid = %s LIMIT 1", (puuid,)
        ).fetchone()
        return row is not None

    def insert_champion_mastery_batch(self, records: list[dict]) -> None:
        for r in records:
            self._execute(
                """INSERT INTO champion_mastery
                   (puuid, champion_id, mastery_level, mastery_points, last_play_time, champion_points_until_next_level)
                   VALUES (%(puuid)s, %(champion_id)s, %(mastery_level)s, %(mastery_points)s,
                           %(last_play_time)s, %(champion_points_until_next_level)s)
                   ON CONFLICT (puuid, champion_id) DO UPDATE SET
                       mastery_level = EXCLUDED.mastery_level, mastery_points = EXCLUDED.mastery_points,
                       last_play_time = EXCLUDED.last_play_time,
                       champion_points_until_next_level = EXCLUDED.champion_points_until_next_level,
                       fetched_at = current_timestamp""",
                r,
            )
        self._maybe_commit()

    def get_champion_mastery_record(self, puuid: str, champion_id: int) -> dict | None:
        row = self._execute(
            "SELECT * FROM champion_mastery WHERE puuid = %s AND champion_id = %s",
            (puuid, champion_id),
        ).fetchone()
        return dict(row) if row else None

    def get_player_recent_stats(self, puuid: str) -> dict | None:
        row = self._execute(
            "SELECT * FROM player_recent_stats WHERE puuid = %s", (puuid,)
        ).fetchone()
        return dict(row) if row else None

    def has_recent_rank(self, puuid: str, hours: int = 24) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        row = self._execute(
            "SELECT 1 FROM summoner_ranks WHERE puuid = %s AND fetched_at > %s",
            (puuid, cutoff),
        ).fetchone()
        return row is not None

    def has_recent_stats(self, puuid: str, hours: int = 24) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        row = self._execute(
            "SELECT 1 FROM player_recent_stats WHERE puuid = %s AND computed_at > %s",
            (puuid, cutoff),
        ).fetchone()
        return row is not None

    def get_all_matches_for_training(self, patch: str | None = None) -> list[str]:
        if patch:
            rows = self._execute(
                """SELECT m.match_id FROM matches m
                   JOIN match_enrichment_status e ON m.match_id = e.match_id
                   WHERE e.enriched = 1 AND m.patch = %s""",
                (patch,),
            ).fetchall()
        else:
            rows = self._execute(
                """SELECT m.match_id FROM matches m
                   JOIN match_enrichment_status e ON m.match_id = e.match_id
                   WHERE e.enriched = 1"""
            ).fetchall()
        return [r["match_id"] for r in rows]

    def compute_recent_stats_from_db(
        self, puuid: str, start_time_ms: int | None = None, exclude_match_id: str | None = None,
        before_time_ms: int | None = None,
    ) -> dict | None:
        conditions = ["m.queue_id = 420", "p.puuid = %s"]
        params: list = [puuid]

        if start_time_ms:
            conditions.append("m.game_creation >= %s")
            params.append(start_time_ms)
        if before_time_ms:
            conditions.append("m.game_creation < %s")
            params.append(before_time_ms)
        if exclude_match_id:
            conditions.append("p.match_id != %s")
            params.append(exclude_match_id)

        where = " AND ".join(conditions)

        rows = self._execute(
            f"""
            SELECT
                p.win,
                p.kills,
                p.deaths,
                p.assists,
                p.total_damage,
                p.cs,
                p.vision_score,
                m.game_duration,
                p.team_id,
                p.match_id,
                p.wards_placed,
                p.wards_killed,
                p.total_damage_taken,
                p.gold_spent,
                p.time_ccing_others,
                p.total_heal,
                p.magic_damage_to_champions,
                p.physical_damage_to_champions,
                p.double_kills,
                p.triple_kills,
                p.quadra_kills,
                p.penta_kills
            FROM participants p
            JOIN matches m ON p.match_id = m.match_id
            WHERE {where}
            ORDER BY m.game_creation DESC
            LIMIT 20
            """,
            params,
        ).fetchall()

        if not rows:
            return None

        team_dmg_cache: dict[str, dict[int, int]] = {}
        for r in rows:
            mid = r["match_id"]
            if mid not in team_dmg_cache:
                team_rows = self._execute(
                    "SELECT team_id, SUM(total_damage) as td FROM participants WHERE match_id = %s GROUP BY team_id",
                    (mid,),
                ).fetchall()
                team_dmg_cache[mid] = {tr["team_id"]: tr["td"] for tr in team_rows}

        stat_rows = []
        for r in rows:
            row_dict = dict(r)
            row_dict["team_total_dmg"] = team_dmg_cache.get(r["match_id"], {}).get(r["team_id"], 0)
            stat_rows.append(row_dict)

        return aggregate_recent_stats(puuid, stat_rows)

    def get_player_champion_stats(self, puuid: str, champion_id: int, patch: str | None = None, exclude_match_id: str | None = None, before_time_ms: int | None = None) -> dict:
        conditions = ["p.puuid = %s", "p.champion_id = %s", "p.match_id != %s"]
        params: list = [puuid, champion_id, exclude_match_id or ""]
        if patch:
            conditions.append("m.patch = %s")
            params.append(patch)
        if before_time_ms:
            conditions.append("m.game_creation < %s")
            params.append(before_time_ms)
        where = " AND ".join(conditions)
        rows = self._execute(
            f"""SELECT p.win FROM participants p
                JOIN matches m ON p.match_id = m.match_id
                WHERE {where}""",
            params,
        ).fetchall()
        if not rows:
            return {"games": 0, "wins": 0, "winrate": 0.0}
        games = len(rows)
        wins = sum(1 for r in rows if r["win"])
        return {"games": games, "wins": wins, "winrate": wins / games}

    def get_player_role_distribution(self, puuid: str, exclude_match_id: str | None = None, before_time_ms: int | None = None) -> dict[str, int]:
        conditions = ["p.puuid = %s", "p.match_id != %s"]
        params: list = [puuid, exclude_match_id or ""]
        if before_time_ms:
            conditions.append("m.game_creation < %s")
            params.append(before_time_ms)
        where = " AND ".join(conditions)
        rows = self._execute(
            f"""SELECT p.team_position, COUNT(*) as cnt FROM participants p
                JOIN matches m ON p.match_id = m.match_id
                WHERE {where}
                GROUP BY p.team_position""",
            params,
        ).fetchall()
        return {r["team_position"]: r["cnt"] for r in rows}

    def get_rank_distribution(self) -> dict[str, int]:
        rows = self._execute(
            """SELECT modal_tier AS tier, COUNT(*) AS cnt FROM (
                SELECT match_id, sr.tier AS modal_tier,
                    ROW_NUMBER() OVER (
                        PARTITION BY p.match_id
                        ORDER BY COUNT(*) DESC,
                            CASE sr.tier
                                WHEN 'IRON' THEN 1 WHEN 'BRONZE' THEN 2 WHEN 'SILVER' THEN 3
                                WHEN 'GOLD' THEN 4 WHEN 'PLATINUM' THEN 5 WHEN 'EMERALD' THEN 6
                                WHEN 'DIAMOND' THEN 7 WHEN 'MASTER' THEN 8 WHEN 'GRANDMASTER' THEN 9
                                WHEN 'CHALLENGER' THEN 10 ELSE 99 END
                    ) AS rn
                FROM participants p
                JOIN summoner_ranks sr ON p.puuid = sr.puuid AND sr.queue_type = 'RANKED_SOLO_5x5'
                GROUP BY p.match_id, sr.tier
            ) sub WHERE rn = 1
            GROUP BY modal_tier
            ORDER BY CASE modal_tier
                WHEN 'IRON' THEN 1 WHEN 'BRONZE' THEN 2 WHEN 'SILVER' THEN 3
                WHEN 'GOLD' THEN 4 WHEN 'PLATINUM' THEN 5 WHEN 'EMERALD' THEN 6
                WHEN 'DIAMOND' THEN 7 WHEN 'MASTER' THEN 8 WHEN 'GRANDMASTER' THEN 9
                WHEN 'CHALLENGER' THEN 10 ELSE 99 END"""
        ).fetchall()
        return {r["tier"]: r["cnt"] for r in rows}

    def get_patch_distribution(self) -> dict[str, int]:
        rows = self._execute(
            """SELECT patch, COUNT(*) as cnt FROM matches GROUP BY patch
               ORDER BY CAST(SPLIT_PART(patch, '.', 1) AS INTEGER),
                        CAST(SPLIT_PART(patch, '.', 2) AS INTEGER)"""
        ).fetchall()
        return {r["patch"]: r["cnt"] for r in rows}

    def get_match_age_range(self) -> tuple[int, int] | None:
        row = self._execute(
            "SELECT MIN(game_creation) as oldest, MAX(game_creation) as newest FROM matches"
        ).fetchone()
        if not row or row["oldest"] is None:
            return None
        return (row["oldest"], row["newest"])

    def get_queue_depth(self) -> int:
        row = self._execute(
            "SELECT COUNT(*) as cnt FROM crawl_queue WHERE status = 'pending'"
        ).fetchone()
        return row["cnt"]

    def insert_model_run(self, run: dict) -> None:
        self._execute(
            """INSERT INTO model_runs
               (run_id, total_matches, train_count, test_count, feature_count,
                patch_min, patch_max, target_mean, hyperparameters,
                best_iteration, best_train_score, training_seconds,
                accuracy, auc_roc, log_loss, tn, fp, fn, tp,
                top_features, notes)
               VALUES (%(run_id)s, %(total_matches)s, %(train_count)s, %(test_count)s, %(feature_count)s,
                       %(patch_min)s, %(patch_max)s, %(target_mean)s, %(hyperparameters)s,
                       %(best_iteration)s, %(best_train_score)s, %(training_seconds)s,
                       %(accuracy)s, %(auc_roc)s, %(log_loss)s, %(tn)s, %(fp)s, %(fn)s, %(tp)s,
                       %(top_features)s, %(notes)s)""",
            run,
        )
        self._maybe_commit()

    def update_model_run(self, run_id: str, updates: dict) -> None:
        set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
        updates["run_id"] = run_id
        self._execute(
            f"UPDATE model_runs SET {set_clause} WHERE run_id = %(run_id)s",
            updates,
        )
        self._maybe_commit()

    def get_model_runs(self, limit: int = 20) -> list[dict]:
        rows = self._execute(
            "SELECT * FROM model_runs ORDER BY created_at DESC LIMIT %s",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stale_enrichment_counts(self, hours: int = 72) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        stale_ranks = self._execute(
            """SELECT COUNT(DISTINCT sr.puuid) as cnt
               FROM summoner_ranks sr
               WHERE sr.fetched_at < %s
               AND NOT EXISTS (
                   SELECT 1 FROM summoner_ranks sr2
                   WHERE sr2.puuid = sr.puuid AND sr2.queue_type = sr.queue_type AND sr2.fetched_at >= %s
               )""",
            (cutoff, cutoff),
        ).fetchone()["cnt"]

        stale_stats = self._execute(
            """SELECT COUNT(*) as cnt FROM player_recent_stats WHERE computed_at < %s""",
            (cutoff,),
        ).fetchone()["cnt"]

        total_enriched = self._execute(
            "SELECT COUNT(DISTINCT puuid) as cnt FROM summoner_ranks"
        ).fetchone()["cnt"]

        return {
            "stale_ranks": stale_ranks,
            "stale_stats": stale_stats,
            "total_enriched": total_enriched,
        }

    def get_stale_enrichment_puuids(self, hours: int = 72, limit: int = 50) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = self._execute(
            """SELECT DISTINCT sr.puuid, sr.summoner_id
               FROM summoner_ranks sr
               WHERE sr.fetched_at < %s
               AND NOT EXISTS (
                   SELECT 1 FROM summoner_ranks sr2
                   WHERE sr2.puuid = sr.puuid AND sr2.queue_type = sr.queue_type AND sr2.fetched_at >= %s
               )
               LIMIT %s""",
            (cutoff, cutoff, limit),
        ).fetchall()
        return [{"puuid": r["puuid"], "summoner_id": r["summoner_id"]} for r in rows]

    def prune_old_ranks(self, keep: int = 2) -> int:
        result = self._execute(
            f"""DELETE FROM summoner_ranks
                WHERE (puuid, queue_type, fetched_at) IN (
                    SELECT puuid, queue_type, fetched_at FROM (
                        SELECT puuid, queue_type, fetched_at,
                            ROW_NUMBER() OVER (PARTITION BY puuid, queue_type ORDER BY fetched_at DESC) as rn
                        FROM summoner_ranks
                    ) sub WHERE rn > {keep}
                )"""
        )
        self._maybe_commit()
        return result.rowcount

    def get_model_run(self, run_id: str) -> dict | None:
        row = self._execute(
            "SELECT * FROM model_runs WHERE run_id = %s", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def insert_match_raw_json(self, match_id: str, raw_json: str) -> None:
        self._execute(
            "INSERT INTO match_raw_json (match_id, raw_json) VALUES (%s, %s::jsonb) ON CONFLICT (match_id) DO NOTHING",
            (match_id, raw_json),
        )
        self._maybe_commit()

    def insert_league_raw_json(self, puuid: str, raw_json: str) -> None:
        self._execute(
            "INSERT INTO league_raw_json (puuid, raw_json) VALUES (%s, %s::jsonb) ON CONFLICT (puuid, fetched_at) DO NOTHING",
            (puuid, raw_json),
        )
        self._maybe_commit()

    def insert_mastery_raw_json(self, puuid: str, champion_id: int, raw_json: str) -> None:
        self._execute(
            """INSERT INTO mastery_raw_json (puuid, champion_id, raw_json) VALUES (%s, %s, %s::jsonb)
               ON CONFLICT (puuid, champion_id) DO UPDATE SET raw_json = EXCLUDED.raw_json, fetched_at = current_timestamp""",
            (puuid, champion_id, raw_json),
        )
        self._maybe_commit()

    def get_match_bans(self, match_id: str) -> list[dict]:
        rows = self._execute(
            "SELECT * FROM match_bans WHERE match_id = %s", (match_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_player_recent_outcomes(
        self, puuid: str, exclude_match_id: str | None = None,
        before_time_ms: int | None = None, limit: int = 10,
    ) -> list[dict]:
        conditions = ["p.puuid = %s", "m.queue_id = 420"]
        params: list = [puuid]
        if exclude_match_id:
            conditions.append("p.match_id != %s")
            params.append(exclude_match_id)
        if before_time_ms:
            conditions.append("m.game_creation < %s")
            params.append(before_time_ms)
        where = " AND ".join(conditions)
        rows = self._execute(
            f"""SELECT p.win, m.game_creation, m.game_duration
                FROM participants p JOIN matches m ON p.match_id = m.match_id
                WHERE {where}
                ORDER BY m.game_creation DESC LIMIT %s""",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]

    def get_champion_patch_winrates(self, patch: str | None = None) -> dict[int, dict]:
        conditions = ["m.queue_id = 420"]
        params: list = []
        if patch:
            conditions.append("m.patch = %s")
            params.append(patch)
        where = " AND ".join(conditions)
        rows = self._execute(
            f"""SELECT p.champion_id, COUNT(*) as games, SUM(p.win) as wins
                FROM participants p JOIN matches m ON p.match_id = m.match_id
                WHERE {where}
                GROUP BY p.champion_id HAVING COUNT(*) >= 5""",
            params,
        ).fetchall()
        return {r["champion_id"]: {"games": r["games"], "winrate": r["wins"] / r["games"]} for r in rows}

    def get_player_top_champions(self, puuid: str, limit: int = 5) -> list[int]:
        rows = self._execute(
            """SELECT champion_id FROM champion_mastery
               WHERE puuid = %s ORDER BY mastery_points DESC LIMIT %s""",
            (puuid, limit),
        ).fetchall()
        return [r["champion_id"] for r in rows]
