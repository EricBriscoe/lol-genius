import { BrowserWindow } from "electron";
import { fetchLiveGameData } from "./api";
import { parseLiveClientData, buildLiveFeatures, snapToSnapshot, type MomentumState } from "../model/features";
import { predict } from "../model/inference";
import { computeTopFactors } from "../model/shap-factors";
import { safeSend } from "../ipc";
import log from "../log";
import { clearTimer } from "../timers";

const logger = log.scope("poller");

const POLL_INTERVAL = 15_000;

let timer: ReturnType<typeof setInterval> | null = null;
let gameId: number | null = null;
let lastGameTime: number | null = null;
let prevDiffs: MomentumState["prevDiffs"] = null;
let peakKillDiff = 0;
let peakTowerDiff = 0;
let prevKillDiffDelta = 0;
let prevBlueKills = 0;
let prevRedKills = 0;
let lastSnapshot: number | null = null;
let pregameSummary: Record<string, number> | null = null;
let lastUpdate: Record<string, unknown> | null = null;
let gameEndedAt: number | null = null;

const GRACE_PERIOD = 30_000;

function resetState(): void {
  gameId = null;
  lastGameTime = null;
  prevDiffs = null;
  peakKillDiff = 0;
  peakTowerDiff = 0;
  prevKillDiffDelta = 0;
  prevBlueKills = 0;
  prevRedKills = 0;
  lastSnapshot = null;
  lastUpdate = null;
  gameEndedAt = null;
}

const send = safeSend;

async function poll(win: BrowserWindow, modelDir: string): Promise<void> {
  const data = await fetchLiveGameData();
  if (!data) {
    if (gameId !== null && lastUpdate) {
      if (gameEndedAt === null) gameEndedAt = Date.now();
      if (Date.now() - gameEndedAt < GRACE_PERIOD) {
        send(win, "prediction-update", { ...lastUpdate, game_ended: true });
        send(win, "connection-status", "connected");
        return;
      }
    }
    send(win, "connection-status", "no_data");
    resetState();
    return;
  }

  gameEndedAt = null;
  send(win, "connection-status", "connected");

  try {
    const newGameId = (data as { gameData?: { gameId?: number } }).gameData?.gameId ?? null;
    const gameIdReset = newGameId !== null && gameId !== null && newGameId !== gameId;
    if (newGameId !== null) gameId = newGameId;

    const gameState = parseLiveClientData(data as Parameters<typeof parseLiveClientData>[0]);
    const currentGameTime = gameState.game_time;
    const timeReset = lastGameTime !== null && currentGameTime < lastGameTime - 30;
    const gameReset = gameIdReset || timeReset;
    lastGameTime = currentGameTime;

    if (gameReset) {
      resetState();
      gameId = newGameId;
      lastGameTime = currentGameTime;
    }

    const killDiff = gameState.kill_diff;
    const towerDiff = gameState.tower_diff;

    const currentSnapshot = snapToSnapshot(currentGameTime);
    const snapshotChanged = lastSnapshot === null || currentSnapshot !== lastSnapshot;

    let killDiffDelta = 0;
    let recentKillShareDiff = 0;

    if (snapshotChanged && prevDiffs) {
      killDiffDelta = killDiff - prevDiffs.kill_diff;
      const blueRecent = gameState.blue_kills - prevBlueKills;
      const redRecent = gameState.red_kills - prevRedKills;
      recentKillShareDiff =
        blueRecent / Math.max(gameState.blue_kills, 1) -
        redRecent / Math.max(gameState.red_kills, 1);
    } else if (prevDiffs) {
      killDiffDelta = prevKillDiffDelta;
    }

    const killDiffAccel = killDiffDelta - prevKillDiffDelta;
    peakKillDiff = Math.max(peakKillDiff, killDiff);
    peakTowerDiff = Math.max(peakTowerDiff, towerDiff);

    const momentum: MomentumState = {
      prevDiffs,
      peakKillDiff,
      peakTowerDiff,
      killDiffAccel,
      recentKillShareDiff,
    };

    const features = buildLiveFeatures(gameState, momentum, pregameSummary ?? undefined);
    logger.debug("Feature vector:", JSON.stringify(features));
    logger.debug("Momentum:", JSON.stringify(momentum));

    if (snapshotChanged) {
      prevDiffs = { kill_diff: killDiff, cs_diff: gameState.cs_diff, tower_diff: towerDiff };
      prevKillDiffDelta = killDiffDelta;
      prevBlueKills = gameState.blue_kills;
      prevRedKills = gameState.red_kills;
      lastSnapshot = currentSnapshot;
    }

    let prob: number;
    try {
      prob = await predict(features, "live");
    } catch (e) {
      logger.error("Prediction failed:", e);
      send(win, "prediction-update", { status: "model_missing", blue_win_probability: null });
      return;
    }

    logger.debug("Probability:", prob);

    const topFactors = await computeTopFactors(modelDir, features, "live");

    const update = {
      status: "ok",
      game_time: gameState.game_time,
      blue_win_probability: prob,
      kill_diff: gameState.kill_diff,
      dragon_diff: gameState.dragon_diff,
      tower_diff: gameState.tower_diff,
      baron_diff: gameState.baron_diff,
      cs_diff: gameState.cs_diff,
      inhibitor_diff: gameState.inhibitor_diff,
      elder_diff: gameState.elder_diff,
      game_reset: gameReset,
      top_factors: topFactors,
    };

    lastUpdate = update;
    send(win, "prediction-update", update);
  } catch (e) {
    logger.error("Poll processing failed:", e);
    send(win, "prediction-update", { status: "poll_error", blue_win_probability: null });
  }
}

export function setPregameData(summary: Record<string, number> | null): void {
  pregameSummary = summary;
}

export function startPolling(win: BrowserWindow, modelDir: string): void {
  stopPolling();
  resetState();
  send(win, "connection-status", "connecting");

  poll(win, modelDir);
  timer = setInterval(() => poll(win, modelDir), POLL_INTERVAL);
}

export function stopPolling(): void {
  timer = clearTimer(timer);
}

export function isPolling(): boolean {
  return timer !== null;
}
