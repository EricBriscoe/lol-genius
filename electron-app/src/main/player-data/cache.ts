import type { LCUClient } from "../lcu-client/api";
import type { LCUGame, LCUParticipant, RankedStats } from "../lcu-client/types";
import type { BrowserWindow } from "electron";
import { safeSend } from "../ipc";
import { getChampionName } from "../model/ddragon";
import * as playerDb from "./db";
import type { MatchRow, RankedStatsRow, MatchHistoryParams, PlayerIdentity } from "./types";
import log from "../log";
import { clearTimer } from "../timers";

const logger = log.scope("player-cache");

let lcuClient: LCUClient | null = null;
let currentPuuid: string | null = null;
let syncTimer: ReturnType<typeof setInterval> | null = null;
let win: BrowserWindow | null = null;

const SYNC_INTERVAL = 3 * 60 * 1000;
const RANKED_STALE_MS = 10 * 60 * 1000;
const MAX_DB_BYTES = 4.5 * 1024 * 1024 * 1024;

function resolvePosition(p: LCUParticipant): string {
  const lane = p.timeline?.lane?.toUpperCase();
  const role = p.timeline?.role?.toUpperCase();
  if (lane === "TOP") return "TOP";
  if (lane === "JUNGLE") return "JUNGLE";
  if (lane === "MIDDLE" || lane === "MID") return "MIDDLE";
  if (lane === "BOTTOM" || lane === "BOT") {
    return role === "SUPPORT" || role === "DUO_SUPPORT" ? "UTILITY" : "BOTTOM";
  }
  return lane ?? "";
}

function parseLCUGames(games: LCUGame[], puuid: string): MatchRow[] {
  return games.map((g) => {
    const identity = g.participantIdentities.find((pi) => pi.player.puuid === puuid);
    const participant = identity
      ? g.participants.find((p) => p.participantId === identity.participantId)
      : null;

    const stats = participant?.stats;
    const cs = (stats?.totalMinionsKilled ?? 0) + (stats?.neutralMinionsKilled ?? 0);

    const participantsSummary = g.participantIdentities.map((pi) => {
      const part = g.participants.find((p) => p.participantId === pi.participantId);
      return {
        puuid: pi.player.puuid,
        gameName: pi.player.gameName,
        tagLine: pi.player.tagLine,
        championId: part?.championId ?? 0,
        teamId: part?.teamId ?? 0,
        kills: part?.stats?.kills ?? 0,
        deaths: part?.stats?.deaths ?? 0,
        assists: part?.stats?.assists ?? 0,
        cs: (part?.stats?.totalMinionsKilled ?? 0) + (part?.stats?.neutralMinionsKilled ?? 0),
        goldEarned: part?.stats?.goldEarned ?? 0,
        totalDamage: part?.stats?.totalDamageDealtToChampions ?? 0,
        win: part?.stats?.win ?? false,
        position: part ? resolvePosition(part) : "",
      };
    });

    return {
      match_id: `${g.gameId}`,
      puuid,
      game_creation: g.gameCreation,
      game_duration: g.gameDuration,
      queue_id: g.queueId,
      champion_id: participant?.championId ?? null,
      champion_name: participant?.championId ? getChampionName(participant.championId) : null,
      team_position: participant ? resolvePosition(participant) : null,
      win: stats ? (stats.win ? 1 : 0) : null,
      kills: stats?.kills ?? null,
      deaths: stats?.deaths ?? null,
      assists: stats?.assists ?? null,
      cs,
      gold_earned: stats?.goldEarned ?? null,
      total_damage: stats?.totalDamageDealtToChampions ?? null,
      vision_score: stats?.visionScore ?? null,
      champion_level: stats?.champLevel ?? null,
      total_damage_taken: stats?.totalDamageTaken ?? null,
      item0: stats?.item0 ?? null,
      item1: stats?.item1 ?? null,
      item2: stats?.item2 ?? null,
      item3: stats?.item3 ?? null,
      item4: stats?.item4 ?? null,
      item5: stats?.item5 ?? null,
      item6: stats?.item6 ?? null,
      summoner_spell1: participant?.spell1Id ?? null,
      summoner_spell2: participant?.spell2Id ?? null,
      participants_json: JSON.stringify(participantsSummary),
    };
  });
}

function resolveMatchChampionNames(match: MatchRow): MatchRow {
  return {
    ...match,
    champion_name: match.champion_id ? getChampionName(match.champion_id) : match.champion_name,
  };
}

export function setLCUClient(client: LCUClient | null): void {
  lcuClient = client;
}

export function setWindow(window: BrowserWindow): void {
  win = window;
}

export async function fetchAndStoreIdentity(): Promise<PlayerIdentity | null> {
  if (!lcuClient) return null;
  const summoner = await lcuClient.getCurrentSummoner();
  if (!summoner) return null;

  const identity: PlayerIdentity = {
    puuid: summoner.puuid,
    gameName: summoner.gameName,
    tagLine: summoner.tagLine,
    summonerId: String(summoner.summonerId),
  };

  playerDb.upsertPlayer(identity);
  currentPuuid = identity.puuid;
  safeSend(win, "player-identity", identity);
  return identity;
}

export function getCurrentPuuid(): string | null {
  return currentPuuid;
}

export async function handleGetMatchHistory(params: MatchHistoryParams): Promise<{
  matches: MatchRow[];
  total: number;
  source: "cache" | "lcu";
  lcuOffline?: boolean;
}> {
  if (!currentPuuid) return { matches: [], total: 0, source: "cache", lcuOffline: true };

  const cached = playerDb.getMatchHistory(currentPuuid, params).map(resolveMatchChampionNames);
  const totalCached = playerDb.getMatchCount(currentPuuid);

  if (cached.length >= params.limit || params.offset + params.limit <= totalCached) {
    return { matches: cached, total: totalCached, source: "cache" };
  }

  if (!lcuClient) {
    return { matches: cached, total: totalCached, source: "cache", lcuOffline: true };
  }

  try {
    const begIndex = totalCached;
    const endIndex = begIndex + 20;
    const lcuResponse = await lcuClient.getMatchHistory(currentPuuid, begIndex, endIndex);

    if (lcuResponse?.games?.games) {
      const rows = parseLCUGames(lcuResponse.games.games, currentPuuid);
      const inserted = playerDb.insertMatches(rows);
      logger.debug(`Fetched ${rows.length} matches from LCU, ${inserted} new`);
    }
  } catch (e) {
    logger.warn("LCU match fetch failed:", e);
  }

  const fresh = playerDb.getMatchHistory(currentPuuid, params).map(resolveMatchChampionNames);
  return { matches: fresh, total: playerDb.getMatchCount(currentPuuid), source: "lcu" };
}

export async function handleGetRankedStats(): Promise<RankedStatsRow[]> {
  if (!currentPuuid) return [];

  const cached = playerDb.getRankedStats(currentPuuid);
  const latestUpdate = cached.reduce((max, s) => Math.max(max, s.updated_at), 0);

  if (cached.length > 0 && Date.now() - latestUpdate < RANKED_STALE_MS) {
    return cached;
  }

  if (!lcuClient) return cached;

  try {
    const rankedResponse = await lcuClient.getCurrentRankedStats() as RankedStats | null;

    if (rankedResponse?.queueMap) {
      const now = Date.now();
      const rows: RankedStatsRow[] = Object.entries(rankedResponse.queueMap)
        .filter(([, entry]) => entry.tier && entry.tier !== "")
        .map(([queueType, entry]) => ({
          puuid: currentPuuid!,
          queue_type: queueType,
          tier: entry.tier,
          division: entry.division,
          lp: entry.leaguePoints,
          wins: entry.wins,
          losses: entry.losses,
          updated_at: now,
        }));
      playerDb.upsertRankedStats(currentPuuid, rows);
    }
  } catch (e) {
    logger.warn("LCU ranked fetch failed:", e);
  }

  return playerDb.getRankedStats(currentPuuid);
}

export function handleGetChampionStats() {
  if (!currentPuuid) return [];
  const stats = playerDb.getChampionStats(currentPuuid);
  return stats.map((s) => ({
    ...s,
    champion_name: getChampionName(s.champion_id),
  }));
}

export function startBackgroundSync(): void {
  stopBackgroundSync();
  if (!currentPuuid) return;

  const puuid = currentPuuid;
  syncTimer = setInterval(async () => {
    if (!lcuClient || !puuid) return;

    try {
      const latestTs = playerDb.getLatestMatchTimestamp(puuid);
      const lcuResponse = await lcuClient.getMatchHistory(puuid, 0, 20);

      if (!lcuResponse?.games?.games) return;

      const allGames = lcuResponse.games.games;
      const newGames = latestTs
        ? allGames.filter((g) => g.gameCreation > latestTs)
        : allGames;

      if (newGames.length > 0) {
        const rows = parseLCUGames(newGames, puuid);
        const inserted = playerDb.insertMatches(rows);
        if (inserted > 0) {
          logger.info(`Background sync: ${inserted} new matches`);
          playerDb.trimIfNeeded(MAX_DB_BYTES);
          safeSend(win, "player-data-update", { newMatches: inserted });
        }
      }
    } catch (e) {
      logger.debug("Background sync error:", e);
    }
  }, SYNC_INTERVAL);
}

export function stopBackgroundSync(): void {
  syncTimer = clearTimer(syncTimer);
}

export async function handleRefreshPlayerData(): Promise<void> {
  if (!lcuClient || !currentPuuid) return;

  try {
    const lcuResponse = await lcuClient.getMatchHistory(currentPuuid, 0, 20);

    if (lcuResponse?.games?.games) {
      const rows = parseLCUGames(lcuResponse.games.games, currentPuuid);
      const inserted = playerDb.insertMatches(rows);
      if (inserted > 0) {
        safeSend(win, "player-data-update", { newMatches: inserted });
      }
    }

    await handleGetRankedStats();
  } catch (e) {
    logger.warn("Manual refresh failed:", e);
  }
}
