import Database from "better-sqlite3";
import { app } from "electron";
import { join } from "path";
import { statSync } from "fs";
import log from "../log";
import type { MatchRow, RankedStatsRow, ChampionStatsAgg, MatchHistoryParams, PlayerIdentity } from "./types";

const logger = log.scope("player-db");

let db: Database.Database | null = null;

export function openDatabase(): void {
  const dbPath = join(app.getPath("userData"), "player-data.db");
  logger.info("Opening player database:", dbPath);
  db = new Database(dbPath);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  migrate();
}

export function closeDatabase(): void {
  db?.close();
  db = null;
}

function migrate(): void {
  if (!db) return;
  db.exec(`
    CREATE TABLE IF NOT EXISTS player (
      puuid TEXT PRIMARY KEY,
      game_name TEXT,
      tag_line TEXT,
      summoner_id TEXT,
      updated_at INTEGER
    );

    CREATE TABLE IF NOT EXISTS matches (
      match_id TEXT PRIMARY KEY,
      puuid TEXT NOT NULL,
      game_creation INTEGER NOT NULL,
      game_duration INTEGER,
      queue_id INTEGER,
      champion_id INTEGER,
      champion_name TEXT,
      team_position TEXT,
      win INTEGER,
      kills INTEGER,
      deaths INTEGER,
      assists INTEGER,
      cs INTEGER,
      gold_earned INTEGER,
      total_damage INTEGER,
      vision_score INTEGER,
      champion_level INTEGER,
      total_damage_taken INTEGER,
      item0 INTEGER, item1 INTEGER, item2 INTEGER,
      item3 INTEGER, item4 INTEGER, item5 INTEGER, item6 INTEGER,
      summoner_spell1 INTEGER,
      summoner_spell2 INTEGER,
      participants_json TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_matches_puuid_creation ON matches(puuid, game_creation DESC);
    CREATE INDEX IF NOT EXISTS idx_matches_champion ON matches(puuid, champion_id);

    CREATE TABLE IF NOT EXISTS ranked_stats (
      puuid TEXT NOT NULL,
      queue_type TEXT NOT NULL,
      tier TEXT,
      division TEXT,
      lp INTEGER,
      wins INTEGER,
      losses INTEGER,
      updated_at INTEGER,
      PRIMARY KEY (puuid, queue_type)
    );
  `);
}

export function upsertPlayer(identity: PlayerIdentity): void {
  if (!db) return;
  db.prepare(`
    INSERT INTO player (puuid, game_name, tag_line, summoner_id, updated_at)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(puuid) DO UPDATE SET
      game_name = excluded.game_name,
      tag_line = excluded.tag_line,
      summoner_id = excluded.summoner_id,
      updated_at = excluded.updated_at
  `).run(identity.puuid, identity.gameName, identity.tagLine, identity.summonerId, Date.now());
}

export function getPlayer(puuid: string): PlayerIdentity | null {
  if (!db) return null;
  const row = db.prepare("SELECT puuid, game_name, tag_line, summoner_id FROM player WHERE puuid = ?").get(puuid) as
    { puuid: string; game_name: string; tag_line: string; summoner_id: string } | undefined;
  if (!row) return null;
  return { puuid: row.puuid, gameName: row.game_name, tagLine: row.tag_line, summonerId: row.summoner_id };
}

export function insertMatches(rows: MatchRow[]): number {
  if (!db || rows.length === 0) return 0;
  const stmt = db.prepare(`
    INSERT INTO matches (
      match_id, puuid, game_creation, game_duration, queue_id,
      champion_id, champion_name, team_position, win,
      kills, deaths, assists, cs, gold_earned, total_damage,
      vision_score, champion_level, total_damage_taken,
      item0, item1, item2, item3, item4, item5, item6,
      summoner_spell1, summoner_spell2, participants_json
    ) VALUES (
      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    ) ON CONFLICT(match_id) DO NOTHING
  `);

  let inserted = 0;
  const tx = db.transaction(() => {
    for (const r of rows) {
      const result = stmt.run(
        r.match_id, r.puuid, r.game_creation, r.game_duration, r.queue_id,
        r.champion_id, r.champion_name, r.team_position, r.win,
        r.kills, r.deaths, r.assists, r.cs, r.gold_earned, r.total_damage,
        r.vision_score, r.champion_level, r.total_damage_taken,
        r.item0, r.item1, r.item2, r.item3, r.item4, r.item5, r.item6,
        r.summoner_spell1, r.summoner_spell2, r.participants_json,
      );
      if (result.changes > 0) inserted++;
    }
  });
  tx();
  return inserted;
}

export function getMatchHistory(puuid: string, params: MatchHistoryParams): MatchRow[] {
  if (!db) return [];

  const conditions = ["puuid = ?"];
  const values: (string | number)[] = [puuid];

  if (params.championId != null) {
    conditions.push("champion_id = ?");
    values.push(params.championId);
  }
  if (params.queueId != null) {
    conditions.push("queue_id = ?");
    values.push(params.queueId);
  }

  const where = conditions.join(" AND ");
  values.push(params.limit, params.offset);

  return db.prepare(
    `SELECT * FROM matches WHERE ${where} ORDER BY game_creation DESC LIMIT ? OFFSET ?`
  ).all(...values) as MatchRow[];
}

export function getMatchCount(puuid: string): number {
  if (!db) return 0;
  const row = db.prepare("SELECT COUNT(*) as cnt FROM matches WHERE puuid = ?").get(puuid) as { cnt: number };
  return row.cnt;
}

export function getLatestMatchTimestamp(puuid: string): number | null {
  if (!db) return null;
  const row = db.prepare(
    "SELECT MAX(game_creation) as latest FROM matches WHERE puuid = ?"
  ).get(puuid) as { latest: number | null };
  return row?.latest ?? null;
}

export function getChampionStats(puuid: string): ChampionStatsAgg[] {
  if (!db) return [];
  return db.prepare(`
    SELECT
      champion_id,
      champion_name,
      COUNT(*) as games,
      SUM(win) as wins,
      ROUND(AVG(kills), 1) as avg_kills,
      ROUND(AVG(deaths), 1) as avg_deaths,
      ROUND(AVG(assists), 1) as avg_assists,
      ROUND(AVG(cs), 0) as avg_cs
    FROM matches
    WHERE puuid = ? AND champion_id IS NOT NULL
    GROUP BY champion_id
    ORDER BY games DESC
  `).all(puuid) as ChampionStatsAgg[];
}

export function upsertRankedStats(puuid: string, stats: RankedStatsRow[]): void {
  if (!db || stats.length === 0) return;
  const stmt = db.prepare(`
    INSERT INTO ranked_stats (puuid, queue_type, tier, division, lp, wins, losses, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(puuid, queue_type) DO UPDATE SET
      tier = excluded.tier,
      division = excluded.division,
      lp = excluded.lp,
      wins = excluded.wins,
      losses = excluded.losses,
      updated_at = excluded.updated_at
  `);

  const tx = db.transaction(() => {
    for (const s of stats) {
      stmt.run(s.puuid, s.queue_type, s.tier, s.division, s.lp, s.wins, s.losses, s.updated_at);
    }
  });
  tx();
}

export function getRankedStats(puuid: string): RankedStatsRow[] {
  if (!db) return [];
  return db.prepare("SELECT * FROM ranked_stats WHERE puuid = ?").all(puuid) as RankedStatsRow[];
}

export function trimIfNeeded(maxBytes: number): void {
  if (!db) return;
  try {
    const dbPath = join(app.getPath("userData"), "player-data.db");
    const size = statSync(dbPath).size;
    if (size <= maxBytes) return;

    logger.info(`DB size ${(size / 1024 / 1024).toFixed(0)}MB exceeds limit, trimming oldest matches`);
    const deleteCount = Math.floor(size / maxBytes * 500);
    db.prepare(`
      DELETE FROM matches WHERE match_id IN (
        SELECT match_id FROM matches ORDER BY game_creation ASC LIMIT ?
      )
    `).run(deleteCount);
    db.exec("VACUUM");
  } catch (e) {
    logger.warn("Trim failed:", e);
  }
}
