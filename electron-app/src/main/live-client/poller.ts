import { BrowserWindow } from "electron";
import { fetchLiveGameData } from "./api";
import { parseLiveClientData, buildLiveFeatures, type GameState, type MomentumState } from "../model/features";
import { predict, getFeatureImportance } from "../model/inference";
import { computeShap } from "../shap/sidecar";

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
let history: { game_time: number; probability: number }[] = [];

function resetState(): void {
  gameId = null;
  lastGameTime = null;
  prevDiffs = null;
  peakKillDiff = 0;
  peakTowerDiff = 0;
  prevKillDiffDelta = 0;
  prevBlueKills = 0;
  prevRedKills = 0;
  history = [];
}

function send(win: BrowserWindow, channel: string, data: unknown): void {
  if (!win.isDestroyed()) {
    win.webContents.send(channel, data);
  }
}

async function poll(win: BrowserWindow, modelDir: string): Promise<void> {
  const data = await fetchLiveGameData();
  if (!data) {
    send(win, "connection-status", "no_data");
    return;
  }

  send(win, "connection-status", "connected");

  const newGameId = (data as { gameData?: { gameId?: number } }).gameData?.gameId ?? null;
  const gameIdReset = newGameId !== null && gameId !== null && newGameId !== gameId;
  if (newGameId !== null) gameId = newGameId;

  const gameState = parseLiveClientData(data as Parameters<typeof parseLiveClientData>[0]);
  const currentGameTime = gameState.game_time;
  const timeReset = lastGameTime !== null && currentGameTime < lastGameTime - 30;
  const gameReset = gameIdReset || timeReset;
  lastGameTime = currentGameTime;

  if (gameReset) {
    prevDiffs = null;
    peakKillDiff = 0;
    peakTowerDiff = 0;
    prevKillDiffDelta = 0;
    prevBlueKills = 0;
    prevRedKills = 0;
    history = [];
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

  const features = buildLiveFeatures(gameState, momentum);

  prevDiffs = { kill_diff: killDiff, cs_diff: gameState.cs_diff, tower_diff: towerDiff };
  prevKillDiffDelta = killDiffDelta;
  prevBlueKills = gameState.blue_kills;
  prevRedKills = gameState.red_kills;

  let prob: number;
  try {
    prob = await predict(features);
  } catch {
    send(win, "prediction-update", { status: "model_missing", blue_win_probability: null });
    return;
  }

  let topFactors: { feature: string; impact: number }[] = [];
  const shapValues = await computeShap(modelDir, features);
  if (shapValues) {
    topFactors = Object.entries(shapValues)
      .map(([feature, impact]) => ({ feature, impact }))
      .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
      .slice(0, 8);
  } else {
    topFactors = getFeatureImportance()
      .slice(0, 8)
      .map((f) => ({ feature: f.feature, impact: f.importance }));
  }

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

  if (gameReset) history = [];
  history.push({ game_time: gameState.game_time, probability: Math.round(prob * 1000) / 10 });
  if (history.length > 100) history = history.slice(-100);

  send(win, "prediction-update", update);
}

export function startPolling(win: BrowserWindow, modelDir: string): void {
  stopPolling();
  resetState();
  send(win, "connection-status", "connecting");

  poll(win, modelDir);
  timer = setInterval(() => poll(win, modelDir), POLL_INTERVAL);
}

export function stopPolling(): void {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

export function isPolling(): boolean {
  return timer !== null;
}
