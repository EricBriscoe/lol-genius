from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from lol_genius.features.stats import aggregate_recent_stats
from lol_genius.features.timeline import SNAPSHOT_SECONDS

from .connection import get_connection

log = logging.getLogger(__name__)

TIER_ORDER = {
    "IRON": 1,
    "BRONZE": 2,
    "SILVER": 3,
    "GOLD": 4,
    "PLATINUM": 5,
    "EMERALD": 6,
    "DIAMOND": 7,
    "MASTER": 8,
    "GRANDMASTER": 9,
    "CHALLENGER": 10,
}


_LATEST_TIER_SUBQUERY = """(
    SELECT DISTINCT ON (puuid) puuid, tier
    FROM summoner_ranks WHERE queue_type = 'RANKED_SOLO_5x5'
    ORDER BY puuid, fetched_at DESC
)"""


def _tier_case_sql(extra: dict[str, int] | None = None) -> str:
    mapping = {**TIER_ORDER, **(extra or {})}
    for name in mapping:
        if not name.isalpha():
            raise ValueError(f"Invalid tier name: {name}")
    return " ".join(f"WHEN '{t}' THEN {v}" for t, v in mapping.items())


class MatchDB:
    def __init__(self, dsn: str | None = None, conn=None):
        if conn is not None:
            self.conn = conn
            self._owned = False
        else:
            self.conn = get_connection(dsn)
            self._owned = True
        self._batch_mode = False

    def _execute(self, sql, params=None):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur

    def _fetchall(self, sql, params=None):
        cur = self._execute(sql, params)
        try:
            return cur.fetchall()
        finally:
            cur.close()

    def _fetchone(self, sql, params=None):
        cur = self._execute(sql, params)
        try:
            return cur.fetchone()
        finally:
            cur.close()

    def _exec(self, sql, params=None) -> int:
        cur = self._execute(sql, params)
        try:
            return cur.rowcount
        finally:
            cur.close()

    @contextmanager
    def transaction(self):
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def close(self):
        if self._owned:
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
        count = self._exec("UPDATE crawl_queue SET status = 'pending' WHERE status = 'processing'")
        self._maybe_commit()
        return max(0, count)

    def match_exists(self, match_id: str) -> bool:
        row = self._fetchone("SELECT 1 FROM matches WHERE match_id = %s", (match_id,))
        return row is not None

    def insert_match(
        self,
        match: dict,
        participants: list[dict],
        bans: list[dict] | None = None,
        objectives: list[dict] | None = None,
        raw_json: str | None = None,
    ) -> None:
        with self.transaction():
            self._execute(
                """INSERT INTO matches
                   (match_id, game_version, patch, game_duration,
                    queue_id, blue_win, game_creation,
                    game_start_timestamp, game_end_timestamp,
                    platform_id)
                   VALUES (
                    %(match_id)s, %(game_version)s, %(patch)s,
                    %(game_duration)s, %(queue_id)s, %(blue_win)s,
                    %(game_creation)s, %(game_start_timestamp)s,
                    %(game_end_timestamp)s, %(platform_id)s)
                   ON CONFLICT (match_id) DO NOTHING""",
                match,
            )
            for p in participants:
                self._execute(
                    """INSERT INTO participants
                       (match_id, puuid, summoner_id, team_id,
                        champion_id, champion_name,
                        team_position, win,
                        kills, deaths, assists, total_damage,
                        cs, vision_score, gold_earned,
                        summoner1_id, summoner2_id,
                        summoner_level,
                        perks_primary_style, perks_sub_style,
                        perks_keystone, perks_offense,
                        perks_flex, perks_defense,
                        magic_damage_to_champions,
                        physical_damage_to_champions,
                        true_damage_to_champions,
                        total_damage_taken,
                        damage_self_mitigated,
                        wards_placed, wards_killed,
                        detector_wards_placed,
                        gold_spent, time_ccing_others,
                        total_heal, total_heals_on_teammates,
                        double_kills, triple_kills,
                        quadra_kills, penta_kills,
                        largest_killing_spree,
                        item0, item1, item2, item3,
                        item4, item5, item6,
                        neutral_minions_killed,
                        total_minions_killed, champion_level)
                       VALUES (
                        %(match_id)s, %(puuid)s,
                        %(summoner_id)s, %(team_id)s,
                        %(champion_id)s, %(champion_name)s,
                        %(team_position)s, %(win)s,
                        %(kills)s, %(deaths)s,
                        %(assists)s, %(total_damage)s,
                        %(cs)s, %(vision_score)s,
                        %(gold_earned)s,
                        %(summoner1_id)s, %(summoner2_id)s,
                        %(summoner_level)s,
                        %(perks_primary_style)s,
                        %(perks_sub_style)s,
                        %(perks_keystone)s, %(perks_offense)s,
                        %(perks_flex)s, %(perks_defense)s,
                        %(magic_damage_to_champions)s,
                        %(physical_damage_to_champions)s,
                        %(true_damage_to_champions)s,
                        %(total_damage_taken)s,
                        %(damage_self_mitigated)s,
                        %(wards_placed)s, %(wards_killed)s,
                        %(detector_wards_placed)s,
                        %(gold_spent)s, %(time_ccing_others)s,
                        %(total_heal)s,
                        %(total_heals_on_teammates)s,
                        %(double_kills)s, %(triple_kills)s,
                        %(quadra_kills)s, %(penta_kills)s,
                        %(largest_killing_spree)s,
                        %(item0)s, %(item1)s, %(item2)s,
                        %(item3)s, %(item4)s, %(item5)s,
                        %(item6)s,
                        %(neutral_minions_killed)s,
                        %(total_minions_killed)s,
                        %(champion_level)s)
                       ON CONFLICT (match_id, puuid)
                       DO NOTHING""",
                    p,
                )

            if bans:
                for b in bans:
                    self._execute(
                        """INSERT INTO match_bans
                           (match_id, team_id, champion_id,
                            pick_turn)
                           VALUES (
                            %(match_id)s, %(team_id)s,
                            %(champion_id)s, %(pick_turn)s)""",
                        b,
                    )

            if objectives:
                for o in objectives:
                    self._execute(
                        """INSERT INTO match_team_objectives
                           (match_id, team_id, objective,
                            first, kills)
                           VALUES (
                            %(match_id)s, %(team_id)s,
                            %(objective)s, %(first)s,
                            %(kills)s)
                           ON CONFLICT
                            (match_id, team_id, objective)
                           DO NOTHING""",
                        o,
                    )

            if raw_json:
                self._execute(
                    """INSERT INTO match_raw_json
                       (match_id, raw_json)
                       VALUES (%s, %s::jsonb)
                       ON CONFLICT (match_id) DO NOTHING""",
                    (match["match_id"], raw_json),
                )

            self._execute(
                """INSERT INTO match_enrichment_status
                   (match_id, enriched) VALUES (%s, 0)
                   ON CONFLICT (match_id) DO NOTHING""",
                (match["match_id"],),
            )

    def insert_summoner_rank(self, rank_data: dict) -> None:
        self._execute(
            """INSERT INTO summoner_ranks
               (puuid, summoner_id, queue_type, tier,
                rank, league_points, wins, losses,
                veteran, inactive, fresh_blood,
                hot_streak)
               VALUES (
                %(puuid)s, %(summoner_id)s,
                %(queue_type)s, %(tier)s, %(rank)s,
                %(league_points)s, %(wins)s, %(losses)s,
                %(veteran)s, %(inactive)s,
                %(fresh_blood)s, %(hot_streak)s)
               ON CONFLICT (puuid, queue_type, fetched_at)
               DO UPDATE SET
                   tier = EXCLUDED.tier,
                   rank = EXCLUDED.rank,
                   league_points = EXCLUDED.league_points,
                   wins = EXCLUDED.wins,
                   losses = EXCLUDED.losses,
                   veteran = EXCLUDED.veteran,
                   inactive = EXCLUDED.inactive,
                   fresh_blood = EXCLUDED.fresh_blood,
                   hot_streak = EXCLUDED.hot_streak""",
            rank_data,
        )
        self._maybe_commit()

    def add_puuids_to_queue(self, puuids: list[str], tier: str = "UNKNOWN") -> int:
        added = 0
        for puuid in puuids:
            cur = self._execute(
                """INSERT INTO crawl_queue (puuid, seed_tier)
                   VALUES (%s, %s)
                   ON CONFLICT (puuid) DO NOTHING""",
                (puuid, tier),
            )
            if cur.rowcount > 0:
                added += 1
        self._maybe_commit()
        return added

    def claim_pending_puuids(
        self, limit: int = 50, tier_weights: dict[str, int] | None = None
    ) -> list[str]:
        with self.transaction():
            cur = self._execute(
                """
                WITH to_claim AS (
                    SELECT puuid, seed_tier FROM crawl_queue
                    WHERE status = 'pending'
                    ORDER BY added_at
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE crawl_queue SET status = 'processing'
                FROM to_claim
                WHERE crawl_queue.puuid = to_claim.puuid
                RETURNING crawl_queue.puuid, to_claim.seed_tier
                """,
                (limit,),
            )
            rows = cur.fetchall()
        if not rows or not tier_weights:
            return [r["puuid"] for r in rows]
        return [
            r["puuid"] for r in sorted(rows, key=lambda r: tier_weights.get(r["seed_tier"], 999))
        ]

    def mark_puuid_done(self, puuid: str) -> None:
        self._execute(
            """UPDATE crawl_queue
               SET status = 'done',
                   processed_at = current_timestamp
               WHERE puuid = %s""",
            (puuid,),
        )
        self._maybe_commit()

    def get_unenriched_matches(self, limit: int = 100) -> list[str]:
        rows = self._fetchall(
            "SELECT match_id FROM match_enrichment_status WHERE enriched = 0 LIMIT %s",
            (limit,),
        )
        return [r["match_id"] for r in rows]

    def mark_match_enriched(self, match_id: str) -> None:
        self._execute(
            """UPDATE match_enrichment_status
               SET enriched = 1,
                   enriched_at = current_timestamp
               WHERE match_id = %s""",
            (match_id,),
        )
        self._maybe_commit()

    def get_match_count(self) -> int:
        row = self._fetchone("SELECT COUNT(*) as cnt FROM matches")
        return row["cnt"]

    def get_queue_stats(self) -> dict:
        rows = self._fetchall("SELECT status, COUNT(*) as cnt FROM crawl_queue GROUP BY status")
        return {r["status"]: r["cnt"] for r in rows}

    def get_queue_stats_by_tier(self) -> dict[str, dict[str, int]]:
        rows = self._fetchall(
            "SELECT seed_tier, status, COUNT(*) as cnt FROM crawl_queue GROUP BY seed_tier, status"
        )
        result: dict[str, dict[str, int]] = {}
        for r in rows:
            tier = r["seed_tier"]
            if tier not in result:
                result[tier] = {}
            result[tier][r["status"]] = r["cnt"]
        return result

    def get_enrichment_stats(self) -> dict:
        row = self._fetchone(
            "SELECT SUM(enriched) as done, COUNT(*) as total FROM match_enrichment_status"
        )
        return {"enriched": row["done"] or 0, "total": row["total"] or 0}

    def get_timeline_stats(self) -> dict:
        row = self._fetchone("""
            SELECT
                (SELECT COUNT(*) FROM match_enrichment_status WHERE enriched = 1) AS total,
                (SELECT COUNT(DISTINCT match_id) FROM match_timelines) AS fetched
        """)
        return {"fetched": row["fetched"] or 0, "total": row["total"] or 0}

    def get_participants_for_match(self, match_id: str) -> list[dict]:
        rows = self._fetchall("SELECT * FROM participants WHERE match_id = %s", (match_id,))
        return [dict(r) for r in rows]

    def get_match(self, match_id: str) -> dict | None:
        row = self._fetchone("SELECT * FROM matches WHERE match_id = %s", (match_id,))
        return dict(row) if row else None

    def get_latest_rank(self, puuid: str, queue_type: str = "RANKED_SOLO_5x5") -> dict | None:
        row = self._fetchone(
            """SELECT * FROM summoner_ranks
               WHERE puuid = %s AND queue_type = %s
               ORDER BY fetched_at DESC LIMIT 1""",
            (puuid, queue_type),
        )
        return dict(row) if row else None

    def has_mastery_data(self, puuid: str) -> bool:
        row = self._fetchone("SELECT 1 FROM champion_mastery WHERE puuid = %s LIMIT 1", (puuid,))
        return row is not None

    def insert_champion_mastery_batch(self, records: list[dict]) -> None:
        for r in records:
            self._execute(
                """INSERT INTO champion_mastery
                   (puuid, champion_id, mastery_level,
                    mastery_points, last_play_time,
                    champion_points_until_next_level)
                   VALUES (
                    %(puuid)s, %(champion_id)s,
                    %(mastery_level)s, %(mastery_points)s,
                    %(last_play_time)s,
                    %(champion_points_until_next_level)s)
                   ON CONFLICT (puuid, champion_id)
                   DO UPDATE SET
                    mastery_level = EXCLUDED.mastery_level,
                    mastery_points = EXCLUDED.mastery_points,
                    last_play_time = EXCLUDED.last_play_time,
                    champion_points_until_next_level =
                        EXCLUDED.champion_points_until_next_level,
                    fetched_at = current_timestamp""",
                r,
            )
        self._maybe_commit()

    def get_champion_mastery_record(self, puuid: str, champion_id: int) -> dict | None:
        row = self._fetchone(
            "SELECT * FROM champion_mastery WHERE puuid = %s AND champion_id = %s",
            (puuid, champion_id),
        )
        return dict(row) if row else None

    def has_recent_rank(self, puuid: str, hours: int = 24) -> bool:
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        row = self._fetchone(
            "SELECT 1 FROM summoner_ranks WHERE puuid = %s AND fetched_at > %s",
            (puuid, cutoff),
        )
        return row is not None

    def get_all_matches_for_training(self, patch: str | None = None) -> list[str]:
        if patch:
            rows = self._fetchall(
                """SELECT m.match_id FROM matches m
                   JOIN match_enrichment_status e ON m.match_id = e.match_id
                   WHERE e.enriched = 1 AND m.patch = %s""",
                (patch,),
            )
        else:
            rows = self._fetchall(
                """SELECT m.match_id FROM matches m
                   JOIN match_enrichment_status e ON m.match_id = e.match_id
                   WHERE e.enriched = 1"""
            )
        return [r["match_id"] for r in rows]

    def compute_recent_stats_from_db(
        self,
        puuid: str,
        start_time_ms: int | None = None,
        exclude_match_id: str | None = None,
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

        rows = self._fetchall(
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
                p.penta_kills,
                COALESCE(team_dmg.td, 0) AS team_total_dmg
            FROM participants p
            JOIN matches m ON p.match_id = m.match_id
            LEFT JOIN LATERAL (
                SELECT SUM(p2.total_damage) AS td
                FROM participants p2
                WHERE p2.match_id = p.match_id AND p2.team_id = p.team_id
            ) team_dmg ON true
            WHERE {where}
            ORDER BY m.game_creation DESC
            LIMIT 20
            """,
            params,
        )

        if not rows:
            return None

        stat_rows = [dict(r) for r in rows]
        return aggregate_recent_stats(puuid, stat_rows)

    def get_player_champion_stats(
        self,
        puuid: str,
        champion_id: int,
        patch: str | None = None,
        exclude_match_id: str | None = None,
        before_time_ms: int | None = None,
    ) -> dict:
        conditions = ["p.puuid = %s", "p.champion_id = %s", "p.match_id != %s"]
        params: list = [puuid, champion_id, exclude_match_id or ""]
        if patch:
            conditions.append("m.patch = %s")
            params.append(patch)
        if before_time_ms:
            conditions.append("m.game_creation < %s")
            params.append(before_time_ms)
        where = " AND ".join(conditions)
        rows = self._fetchall(
            f"""SELECT p.win FROM participants p
                JOIN matches m ON p.match_id = m.match_id
                WHERE {where}""",
            params,
        )
        if not rows:
            return {"games": 0, "wins": 0, "winrate": 0.0}
        games = len(rows)
        wins = sum(1 for r in rows if r["win"])
        return {"games": games, "wins": wins, "winrate": wins / games}

    def get_player_role_distribution(
        self,
        puuid: str,
        exclude_match_id: str | None = None,
        before_time_ms: int | None = None,
    ) -> dict[str, int]:
        conditions = ["p.puuid = %s", "p.match_id != %s"]
        params: list = [puuid, exclude_match_id or ""]
        if before_time_ms:
            conditions.append("m.game_creation < %s")
            params.append(before_time_ms)
        where = " AND ".join(conditions)
        rows = self._fetchall(
            f"""SELECT p.team_position, COUNT(*) as cnt FROM participants p
                JOIN matches m ON p.match_id = m.match_id
                WHERE {where}
                GROUP BY p.team_position""",
            params,
        )
        return {r["team_position"]: r["cnt"] for r in rows}

    def get_rank_distribution(self) -> dict[str, int]:
        tc = _tier_case_sql()
        rows = self._fetchall(
            f"""SELECT modal_tier AS tier, COUNT(*) AS cnt FROM (
                SELECT match_id, sr.tier AS modal_tier,
                    ROW_NUMBER() OVER (
                        PARTITION BY p.match_id
                        ORDER BY COUNT(*) DESC,
                            CASE sr.tier {tc} ELSE 99 END
                    ) AS rn
                FROM participants p
                JOIN summoner_ranks sr ON p.puuid = sr.puuid AND sr.queue_type = 'RANKED_SOLO_5x5'
                GROUP BY p.match_id, sr.tier
            ) sub WHERE rn = 1
            GROUP BY modal_tier
            ORDER BY CASE modal_tier {tc} ELSE 99 END"""
        )
        return {r["tier"]: r["cnt"] for r in rows}

    def get_patch_distribution(self) -> dict[str, int]:
        rows = self._fetchall(
            """SELECT patch, COUNT(*) as cnt FROM matches GROUP BY patch
               ORDER BY CAST(SPLIT_PART(patch, '.', 1) AS INTEGER),
                        CAST(SPLIT_PART(patch, '.', 2) AS INTEGER)"""
        )
        return {r["patch"]: r["cnt"] for r in rows}

    def get_match_age_range(self) -> tuple[int, int] | None:
        row = self._fetchone(
            "SELECT MIN(game_creation) as oldest, MAX(game_creation) as newest FROM matches"
        )
        if not row or row["oldest"] is None:
            return None
        return (row["oldest"], row["newest"])

    def get_queue_depth(self) -> int:
        row = self._fetchone("SELECT COUNT(*) as cnt FROM crawl_queue WHERE status = 'pending'")
        return row["cnt"]

    def insert_model_run(self, run: dict) -> None:
        self._execute(
            """INSERT INTO model_runs
               (run_id, model_type, total_matches,
                train_count, test_count, feature_count,
                patch_min, patch_max, target_mean,
                hyperparameters,
                best_iteration, best_train_score,
                training_seconds,
                accuracy, auc_roc, log_loss,
                tn, fp, fn, tp,
                top_features, notes)
               VALUES (
                %(run_id)s, %(model_type)s,
                %(total_matches)s, %(train_count)s,
                %(test_count)s, %(feature_count)s,
                %(patch_min)s, %(patch_max)s,
                %(target_mean)s, %(hyperparameters)s,
                %(best_iteration)s,
                %(best_train_score)s,
                %(training_seconds)s,
                %(accuracy)s, %(auc_roc)s,
                %(log_loss)s, %(tn)s, %(fp)s,
                %(fn)s, %(tp)s,
                %(top_features)s, %(notes)s)""",
            run,
        )
        self._maybe_commit()

    def update_model_run(self, run_id: str, updates: dict) -> None:
        from psycopg2.extras import Json

        _jsonb_cols = {"time_window_metrics"}
        for k in _jsonb_cols:
            if k in updates and updates[k] is not None and not isinstance(updates[k], str):
                updates[k] = Json(updates[k])
        set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
        updates["run_id"] = run_id
        self._execute(
            f"UPDATE model_runs SET {set_clause} WHERE run_id = %(run_id)s",
            updates,
        )
        self._maybe_commit()

    def get_model_runs(self, limit: int = 20, model_type: str | None = None) -> list[dict]:
        if model_type:
            rows = self._fetchall(
                "SELECT * FROM model_runs WHERE model_type = %s ORDER BY created_at DESC LIMIT %s",
                (model_type, limit),
            )
        else:
            rows = self._fetchall(
                "SELECT * FROM model_runs ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
        return [dict(r) for r in rows]

    def get_stale_enrichment_counts(self, hours: int = 72) -> dict:
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        stale_ranks = self._fetchone(
            """SELECT COUNT(DISTINCT sr.puuid) as cnt
               FROM summoner_ranks sr
               WHERE sr.fetched_at < %s
               AND NOT EXISTS (
                   SELECT 1 FROM summoner_ranks sr2
                   WHERE sr2.puuid = sr.puuid
                     AND sr2.queue_type = sr.queue_type
                     AND sr2.fetched_at >= %s
               )""",
            (cutoff, cutoff),
        )["cnt"]

        total_enriched = self._fetchone("SELECT COUNT(DISTINCT puuid) as cnt FROM summoner_ranks")[
            "cnt"
        ]

        return {
            "stale_ranks": stale_ranks,
            "total_enriched": total_enriched,
        }

    def get_stale_enrichment_puuids(self, hours: int = 72, limit: int = 50) -> list[dict]:
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        rows = self._fetchall(
            """SELECT DISTINCT sr.puuid, sr.summoner_id
               FROM summoner_ranks sr
               WHERE sr.fetched_at < %s
               AND NOT EXISTS (
                   SELECT 1 FROM summoner_ranks sr2
                   WHERE sr2.puuid = sr.puuid
                     AND sr2.queue_type = sr.queue_type
                     AND sr2.fetched_at >= %s
               )
               LIMIT %s""",
            (cutoff, cutoff, limit),
        )
        return [{"puuid": r["puuid"], "summoner_id": r["summoner_id"]} for r in rows]

    def prune_old_ranks(self, keep: int = 2) -> int:
        count = self._exec(
            f"""DELETE FROM summoner_ranks
                WHERE (puuid, queue_type, fetched_at) IN (
                    SELECT puuid, queue_type, fetched_at FROM (
                        SELECT puuid, queue_type, fetched_at,
                            ROW_NUMBER() OVER (
                                PARTITION BY puuid, queue_type
                                ORDER BY fetched_at DESC
                            ) as rn
                        FROM summoner_ranks
                    ) sub WHERE rn > {keep}
                )"""
        )
        self._maybe_commit()
        return count

    def get_model_run(self, run_id: str) -> dict | None:
        row = self._fetchone("SELECT * FROM model_runs WHERE run_id = %s", (run_id,))
        return dict(row) if row else None

    def insert_match_raw_json(self, match_id: str, raw_json: str) -> None:
        self._execute(
            """INSERT INTO match_raw_json (match_id, raw_json)
               VALUES (%s, %s::jsonb)
               ON CONFLICT (match_id) DO NOTHING""",
            (match_id, raw_json),
        )
        self._maybe_commit()

    def insert_league_raw_json(self, puuid: str, raw_json: str) -> None:
        self._execute(
            """INSERT INTO league_raw_json (puuid, raw_json)
               VALUES (%s, %s::jsonb)
               ON CONFLICT (puuid, fetched_at) DO NOTHING""",
            (puuid, raw_json),
        )
        self._maybe_commit()

    def insert_mastery_raw_json(self, puuid: str, champion_id: int, raw_json: str) -> None:
        self._execute(
            """INSERT INTO mastery_raw_json (puuid, champion_id, raw_json)
               VALUES (%s, %s, %s::jsonb)
               ON CONFLICT (puuid, champion_id) DO UPDATE SET
                   raw_json = EXCLUDED.raw_json,
                   fetched_at = current_timestamp""",
            (puuid, champion_id, raw_json),
        )
        self._maybe_commit()

    def insert_timeline_raw_json(self, match_id: str, raw_json: str) -> None:
        self._execute(
            """INSERT INTO timeline_raw_json (match_id, raw_json)
               VALUES (%s, %s::jsonb)
               ON CONFLICT (match_id) DO NOTHING""",
            (match_id, raw_json),
        )
        self._maybe_commit()

    def get_all_timeline_raw_json(self) -> list[tuple[str, dict]]:
        rows = self._fetchall("SELECT match_id, raw_json FROM timeline_raw_json")
        return [(r["match_id"], r["raw_json"]) for r in rows]

    def get_match_bans(self, match_id: str) -> list[dict]:
        rows = self._fetchall("SELECT * FROM match_bans WHERE match_id = %s", (match_id,))
        return [dict(r) for r in rows]

    def get_player_recent_outcomes(
        self,
        puuid: str,
        exclude_match_id: str | None = None,
        before_time_ms: int | None = None,
        limit: int = 10,
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
        rows = self._fetchall(
            f"""SELECT p.win, m.game_creation, m.game_duration
                FROM participants p JOIN matches m ON p.match_id = m.match_id
                WHERE {where}
                ORDER BY m.game_creation DESC LIMIT %s""",
            params + [limit],
        )
        return [dict(r) for r in rows]

    def get_champion_patch_winrates(self, patch: str | None = None) -> dict[int, dict]:
        conditions = ["m.queue_id = 420"]
        params: list = []
        if patch:
            conditions.append("m.patch = %s")
            params.append(patch)
        where = " AND ".join(conditions)
        rows = self._fetchall(
            f"""SELECT p.champion_id, COUNT(*) as games, SUM(p.win) as wins
                FROM participants p JOIN matches m ON p.match_id = m.match_id
                WHERE {where}
                GROUP BY p.champion_id HAVING COUNT(*) >= 5""",
            params,
        )
        return {
            r["champion_id"]: {"games": r["games"], "winrate": r["wins"] / r["games"]} for r in rows
        }

    def get_champion_stats(self, patch: str | None = None, tier: str | None = None) -> list[dict]:
        conditions = ["m.queue_id = 420"]
        params: list = []
        if patch:
            conditions.append("m.patch = %s")
            params.append(patch)
        tier_join = ""
        if tier:
            tier_join = f"JOIN {_LATEST_TIER_SUBQUERY} sr ON sr.puuid = p.puuid"
            conditions.append("sr.tier = %s")
            params.append(tier)
        where = " AND ".join(conditions)
        rows = self._fetchall(
            f"""SELECT p.champion_id, p.champion_name, p.team_position,
                       COUNT(*) as games, SUM(p.win) as wins,
                       AVG(p.kills) as avg_kills, AVG(p.deaths) as avg_deaths,
                       AVG(p.assists) as avg_assists, AVG(p.cs) as avg_cs,
                       AVG(p.gold_earned) as avg_gold, AVG(p.total_damage) as avg_damage,
                       AVG(p.vision_score) as avg_vision
                FROM participants p
                JOIN matches m ON p.match_id = m.match_id
                {tier_join}
                WHERE {where}
                GROUP BY p.champion_id, p.champion_name, p.team_position
                HAVING COUNT(*) >= 5""",
            params,
        )
        champs: dict[int, dict] = {}
        for r in rows:
            cid = r["champion_id"]
            if cid not in champs:
                champs[cid] = {
                    "champion_id": cid,
                    "champion_name": r["champion_name"],
                    "games": 0,
                    "wins": 0,
                    "total_kills": 0.0,
                    "total_deaths": 0.0,
                    "total_assists": 0.0,
                    "total_cs": 0.0,
                    "total_gold": 0.0,
                    "total_damage": 0.0,
                    "total_vision": 0.0,
                    "positions": {},
                }
            c = champs[cid]
            g = r["games"]
            c["games"] += g
            c["wins"] += r["wins"]
            c["total_kills"] += float(r["avg_kills"]) * g
            c["total_deaths"] += float(r["avg_deaths"]) * g
            c["total_assists"] += float(r["avg_assists"]) * g
            c["total_cs"] += float(r["avg_cs"]) * g
            c["total_gold"] += float(r["avg_gold"]) * g
            c["total_damage"] += float(r["avg_damage"]) * g
            c["total_vision"] += float(r["avg_vision"]) * g
            pos = r["team_position"]
            if pos:
                c["positions"][pos] = g
        result = []
        for c in champs.values():
            g = c["games"]
            result.append(
                {
                    "champion_id": c["champion_id"],
                    "champion_name": c["champion_name"],
                    "games": g,
                    "wins": c["wins"],
                    "avg_kills": round(c["total_kills"] / g, 1),
                    "avg_deaths": round(c["total_deaths"] / g, 1),
                    "avg_assists": round(c["total_assists"] / g, 1),
                    "avg_cs": round(c["total_cs"] / g, 0),
                    "avg_gold": round(c["total_gold"] / g, 0),
                    "avg_damage": round(c["total_damage"] / g, 0),
                    "avg_vision": round(c["total_vision"] / g, 1),
                    "positions": c["positions"],
                }
            )
        return result

    def get_champion_ban_stats(
        self, patch: str | None = None, tier: str | None = None
    ) -> dict[int, int]:
        conditions = ["m.queue_id = 420"]
        params: list = []
        if patch:
            conditions.append("m.patch = %s")
            params.append(patch)
        if tier:
            conditions.append(f"""b.match_id IN (
                SELECT DISTINCT p.match_id FROM participants p
                JOIN {_LATEST_TIER_SUBQUERY} sr ON sr.puuid = p.puuid
                WHERE sr.tier = %s
            )""")
            params.append(tier)
        where = " AND ".join(conditions)
        rows = self._fetchall(
            f"""SELECT b.champion_id, COUNT(*) as bans
                FROM match_bans b JOIN matches m ON b.match_id = m.match_id
                WHERE {where}
                GROUP BY b.champion_id""",
            params,
        )
        return {r["champion_id"]: r["bans"] for r in rows}

    def get_tier_match_count(self, patch: str | None = None, tier: str | None = None) -> int:
        conditions = ["m.queue_id = 420"]
        params: list = []
        if patch:
            conditions.append("m.patch = %s")
            params.append(patch)
        if tier:
            conditions.append(f"""p.match_id IN (
                SELECT DISTINCT p2.match_id FROM participants p2
                JOIN {_LATEST_TIER_SUBQUERY} sr ON sr.puuid = p2.puuid
                WHERE sr.tier = %s
            )""")
            params.append(tier)
        where = " AND ".join(conditions)
        row = self._fetchone(
            f"""SELECT COUNT(DISTINCT m.match_id) as cnt
                FROM matches m
                JOIN participants p ON p.match_id = m.match_id
                WHERE {where}""",
            params,
        )
        return row["cnt"]

    def get_player_top_champions(self, puuid: str, limit: int = 5) -> list[int]:
        rows = self._fetchall(
            """SELECT champion_id FROM champion_mastery
               WHERE puuid = %s ORDER BY mastery_points DESC LIMIT %s""",
            (puuid, limit),
        )
        return [r["champion_id"] for r in rows]

    def save_timeline_snapshots(self, match_id: str, snapshots: list[dict]) -> None:
        for s in snapshots:
            self._execute(
                """INSERT INTO match_timelines
                   (match_id, snapshot_seconds, blue_gold, red_gold, blue_cs, red_cs,
                    blue_kills, red_kills, blue_towers, red_towers, blue_dragons, red_dragons,
                    blue_barons, red_barons, blue_heralds, red_heralds,
                    blue_inhibitors, red_inhibitors, blue_elder, red_elder,
                    first_blood_blue, first_tower_blue, first_dragon_blue,
                    blue_avg_level, red_avg_level, blue_max_level, red_max_level)
                   VALUES (%(match_id)s, %(snapshot_seconds)s, %(blue_gold)s, %(red_gold)s,
                           %(blue_cs)s, %(red_cs)s, %(blue_kills)s, %(red_kills)s,
                           %(blue_towers)s, %(red_towers)s, %(blue_dragons)s, %(red_dragons)s,
                           %(blue_barons)s, %(red_barons)s, %(blue_heralds)s, %(red_heralds)s,
                           %(blue_inhibitors)s, %(red_inhibitors)s, %(blue_elder)s, %(red_elder)s,
                           %(first_blood_blue)s, %(first_tower_blue)s, %(first_dragon_blue)s,
                           %(blue_avg_level)s, %(red_avg_level)s,
                           %(blue_max_level)s, %(red_max_level)s)
                   ON CONFLICT (match_id, snapshot_seconds) DO NOTHING""",
                {"match_id": match_id, **s},
            )
        self._maybe_commit()

    def get_match_ids_without_timelines(self) -> list[str]:
        placeholders = ",".join(["%s"] * len(SNAPSHOT_SECONDS))
        rows = self._fetchall(
            f"""SELECT m.match_id FROM matches m
               JOIN match_enrichment_status e ON m.match_id = e.match_id
               WHERE e.enriched = 1
               AND NOT EXISTS (
                   SELECT 1 FROM match_timelines t
                   WHERE t.match_id = m.match_id
                   AND t.snapshot_seconds IN ({placeholders})
               )""",
            tuple(SNAPSHOT_SECONDS),
        )
        return [r["match_id"] for r in rows]

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self._fetchone("SELECT value FROM settings WHERE key = %s", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self._execute(
            """INSERT INTO settings (key, value) VALUES (%s, %s)
               ON CONFLICT (key) DO UPDATE SET
                   value = EXCLUDED.value,
                   updated_at = current_timestamp""",
            (key, value),
        )
        self._maybe_commit()

    def get_timeline_training_data(self) -> list[dict]:
        placeholders = ",".join(["%s"] * len(SNAPSHOT_SECONDS))
        rows = self._fetchall(
            f"""SELECT mt.match_id, m.game_creation,
                      mt.snapshot_seconds AS game_time_seconds,
                      mt.blue_gold, mt.red_gold,
                      mt.blue_cs, mt.red_cs,
                      mt.blue_kills, mt.red_kills,
                      mt.blue_towers, mt.red_towers,
                      mt.blue_dragons, mt.red_dragons,
                      mt.blue_barons, mt.red_barons,
                      mt.blue_heralds, mt.red_heralds,
                      mt.blue_inhibitors, mt.red_inhibitors,
                      mt.blue_elder, mt.red_elder,
                      mt.first_blood_blue, mt.first_tower_blue, mt.first_dragon_blue,
                      mt.blue_avg_level, mt.red_avg_level,
                      mt.blue_max_level, mt.red_max_level,
                      m.blue_win, m.pregame_blue_win_prob
               FROM match_timelines mt
               JOIN matches m ON mt.match_id = m.match_id
               WHERE mt.snapshot_seconds IN ({placeholders})
               ORDER BY mt.match_id, mt.snapshot_seconds""",
            tuple(SNAPSHOT_SECONDS),
        )
        return [dict(r) for r in rows]

    def get_match_pregame_participants(self, match_ids: list[str]) -> list[dict]:
        if not match_ids:
            return []
        rows = self._fetchall(
            """SELECT p.match_id, p.team_id, p.champion_id, p.champion_name, p.puuid,
                      sr.tier, sr.rank, sr.league_points, sr.wins, sr.losses,
                      COALESCE(sr.hot_streak, 0) AS hot_streak,
                      COALESCE(sr.veteran, 0) AS veteran,
                      COALESCE(cm.mastery_points, 0) AS mastery_points,
                      COALESCE(cm.mastery_level, 0) AS mastery_level
               FROM participants p
               LEFT JOIN (
                   SELECT DISTINCT ON (puuid) puuid, tier, rank, league_points, wins, losses,
                          hot_streak, veteran
                   FROM summoner_ranks
                   WHERE queue_type = 'RANKED_SOLO_5x5'
                   ORDER BY puuid, fetched_at DESC
               ) sr ON sr.puuid = p.puuid
               LEFT JOIN champion_mastery cm ON cm.puuid = p.puuid
                   AND cm.champion_id = p.champion_id
               WHERE p.match_id = ANY(%s)""",
            (match_ids,),
        )
        return [dict(r) for r in rows]

    def get_ranks_and_mastery_by_puuids(self, puuids: list[str]) -> tuple[list[dict], list[dict]]:
        if not puuids:
            return [], []
        ranks = self._fetchall(
            """SELECT DISTINCT ON (puuid) puuid, tier, rank, league_points, wins, losses,
                      COALESCE(hot_streak, 0) AS hot_streak,
                      COALESCE(veteran, 0) AS veteran
               FROM summoner_ranks
               WHERE puuid = ANY(%s) AND queue_type = 'RANKED_SOLO_5x5'
               ORDER BY puuid, fetched_at DESC""",
            (puuids,),
        )
        masteries = self._fetchall(
            """SELECT puuid, champion_id, mastery_points, mastery_level
               FROM champion_mastery WHERE puuid = ANY(%s)""",
            (puuids,),
        )
        return [dict(r) for r in ranks], [dict(r) for r in masteries]

    def get_champion_scaling_scores(
        self, prior_strength: int = 10, min_games: int = 20
    ) -> dict[int, float]:
        rows = self._fetchall(
            """SELECT p.champion_id,
                      SUM(CASE WHEN m.game_duration >= 1500
                          AND p.win::boolean THEN 1 ELSE 0 END
                      ) AS late_wins,
                      SUM(CASE WHEN m.game_duration >= 1500
                          THEN 1 ELSE 0 END
                      ) AS late_games,
                      SUM(CASE WHEN m.game_duration < 1500
                          AND p.win::boolean THEN 1 ELSE 0 END
                      ) AS early_wins,
                      SUM(CASE WHEN m.game_duration < 1500
                          THEN 1 ELSE 0 END
                      ) AS early_games,
                      COUNT(*) AS total_games
               FROM participants p
               JOIN matches m ON p.match_id = m.match_id
               WHERE m.queue_id = 420
               GROUP BY p.champion_id"""
        )
        prior = 0.5
        scores: dict[int, float] = {}
        for r in rows:
            if r["total_games"] < min_games:
                continue
            late_wr = (r["late_wins"] + prior * prior_strength) / (r["late_games"] + prior_strength)
            early_wr = (r["early_wins"] + prior * prior_strength) / (
                r["early_games"] + prior_strength
            )
            scores[int(r["champion_id"])] = round(late_wr - early_wr, 4)
        return scores

    def get_crawl_rate_history(self, days: int = 7) -> list[dict]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        rows = self._fetchall(
            """SELECT date_trunc('hour', crawled_at) AS hour, COUNT(*) AS count
               FROM matches
               WHERE crawled_at >= %s
               GROUP BY date_trunc('hour', crawled_at)
               ORDER BY hour""",
            (cutoff,),
        )
        return [{"hour": r["hour"], "count": r["count"]} for r in rows]

    def bulk_update_pregame_probs(self, pairs: list[tuple[str, float]]) -> None:
        for match_id, prob in pairs:
            self._execute(
                "UPDATE matches SET pregame_blue_win_prob = %s WHERE match_id = %s",
                (prob, match_id),
            )
        self._maybe_commit()


@contextmanager
def pooled_db(pool):
    conn = pool.getconn()
    try:
        yield MatchDB(conn=conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)
