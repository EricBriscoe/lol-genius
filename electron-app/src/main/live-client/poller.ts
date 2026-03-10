import { BrowserWindow } from "electron";
import { fetchLiveGameData } from "./api";
import { parseLiveClientData, buildLiveFeatures, type MomentumState } from "../model/features";
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
let pregameProb = 0.5;
let pregameSummary: Record<string, number> | null = null;

function resetState(): void {
  gameId = null;
  lastGameTime = null;
  prevDiffs = null;
  peakKillDiff = 0;
  peakTowerDiff = 0;
  prevKillDiffDelta = 0;
  prevBlueKills = 0;
  prevRedKills = 0;
}

const send = safeSend;

async function poll(win: BrowserWindow, modelDir: string): Promise<void> {
  const data = await fetchLiveGameData();
  if (!data) {
    send(win, "connection-status", "no_data");
    return;
  }

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

    let killDiffDelta = 0;
    let recentKillShareDiff = 0;

    if (prevDiffs) {
      killDiffDelta = killDiff - prevDiffs.kill_diff;
      const blueRecent = gameState.blue_kills - prevBlueKills;
      const redRecent = gameState.red_kills - prevRedKills;
      recentKillShareDiff =
        blueRecent / Math.max(gameState.blue_kills, 1) -
        redRecent / Math.max(gameState.red_kills, 1);
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

    const features = buildLiveFeatures(gameState, momentum, pregameProb, pregameSummary ?? undefined);
    logger.debug("Feature vector:", JSON.stringify(features));
    logger.debug("Momentum:", JSON.stringify(momentum));

    prevDiffs = { kill_diff: killDiff, cs_diff: gameState.cs_diff, tower_diff: towerDiff };
    prevKillDiffDelta = killDiffDelta;
    prevBlueKills = gameState.blue_kills;
    prevRedKills = gameState.red_kills;

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

    send(win, "prediction-update", update);
  } catch (e) {
    logger.error("Poll processing failed:", e);
    send(win, "prediction-update", { status: "poll_error", blue_win_probability: null });
  }
}

export function setPregameData(prob: number | null, summary: Record<string, number> | null): void {
  pregameProb = prob ?? 0.5;
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
