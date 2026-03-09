import { ipcMain, type BrowserWindow } from "electron";
import type { LCUClient } from "../lcu-client/api";
import * as playerDb from "./db";
import * as cache from "./cache";
import type { MatchHistoryParams } from "./types";
import log from "../log";

const logger = log.scope("player-data");

export function initPlayerData(window: BrowserWindow): void {
  logger.info("Initializing player data service");
  playerDb.openDatabase();
  cache.setWindow(window);

  ipcMain.handle("get-player-identity", () => {
    const puuid = cache.getCurrentPuuid();
    if (!puuid) return null;
    return playerDb.getPlayer(puuid);
  });

  ipcMain.handle("get-match-history", (_, params: MatchHistoryParams) =>
    cache.handleGetMatchHistory(params),
  );

  ipcMain.handle("get-champion-stats", () =>
    cache.handleGetChampionStats(),
  );

  ipcMain.handle("get-ranked-stats", () =>
    cache.handleGetRankedStats(),
  );

  ipcMain.handle("refresh-player-data", () =>
    cache.handleRefreshPlayerData(),
  );
}

export async function onLCUConnected(client: LCUClient): Promise<void> {
  cache.setLCUClient(client);
  try {
    await cache.fetchAndStoreIdentity();
    cache.startBackgroundSync();
  } catch (e) {
    logger.warn("Failed to fetch player identity:", e);
  }
}

export function onLCUDisconnected(): void {
  cache.setLCUClient(null);
  cache.stopBackgroundSync();
}

export function shutdownPlayerData(): void {
  cache.stopBackgroundSync();
  playerDb.closeDatabase();
}
