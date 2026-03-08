import { BrowserWindow } from "electron";
import { findLockfile, readLockfile, watchLockfile } from "./lockfile";
import { createLCUClient, type LCUClient } from "./api";
import type { LCUCredentials, ChampSelectSession, RankedStats } from "./types";
import { buildPregameFeatures, getPregameSummaryFromFeatures } from "../model/pregame-features";
import { predict, isModelLoaded, getFeatureNames, getFeatureImportance } from "../model/inference";
import { computeShap } from "../shap/sidecar";
import * as ddragon from "../model/ddragon";
import log from "../log";

const logger = log.scope("lcu-poller");

type LCUState = "disconnected" | "connected" | "champ_select" | "game_start";

const LOCKFILE_POLL_INTERVAL = 5_000;
const GAMEFLOW_POLL_INTERVAL = 3_000;
const CHAMP_SELECT_POLL_INTERVAL = 2_000;

let state: LCUState = "disconnected";
let client: LCUClient | null = null;
let lockfilePollTimer: ReturnType<typeof setInterval> | null = null;
let gameflowTimer: ReturnType<typeof setInterval> | null = null;
let champSelectTimer: ReturnType<typeof setInterval> | null = null;
let stopLockfileWatch: (() => void) | null = null;
let win: BrowserWindow | null = null;
let modelDir: string | null = null;
let lastPregameProb: number | null = null;
let lastPregameSummary: Record<string, number> | null = null;
let cachedRankedStats: RankedStats | null = null;

function send(channel: string, data: unknown): void {
  if (win && !win.isDestroyed()) {
    win.webContents.send(channel, data);
  }
}

function setState(next: LCUState): void {
  if (state === next) return;
  logger.debug("LCU state:", state, "→", next);
  state = next;
}

function stopAllTimers(): void {
  if (lockfilePollTimer) { clearInterval(lockfilePollTimer); lockfilePollTimer = null; }
  if (gameflowTimer) { clearInterval(gameflowTimer); gameflowTimer = null; }
  if (champSelectTimer) { clearInterval(champSelectTimer); champSelectTimer = null; }
}

function onDisconnected(): void {
  stopAllTimers();
  client = null;
  cachedRankedStats = null;
  setState("disconnected");
  send("connection-status", "lcu_disconnected");
  startLockfilePolling();
}

function onConnected(creds: LCUCredentials): void {
  stopAllTimers();
  client = createLCUClient(creds);
  setState("connected");
  send("connection-status", "lcu_connected");
  startGameflowPolling();
}

function startLockfilePolling(): void {
  if (lockfilePollTimer) return;

  const check = () => {
    const path = findLockfile();
    if (path) {
      const creds = readLockfile(path);
      if (creds) {
        onConnected(creds);
        return;
      }
    }
  };

  check();
  if (state === "disconnected") {
    lockfilePollTimer = setInterval(check, LOCKFILE_POLL_INTERVAL);
  }
}

function startGameflowPolling(): void {
  if (gameflowTimer) return;

  const poll = async () => {
    if (!client) { onDisconnected(); return; }

    const phase = await client.getGameflowPhase();
    if (phase === null) {
      onDisconnected();
      return;
    }

    logger.debug("Gameflow phase:", phase);

    if (phase === "ChampSelect") {
      if (state !== "champ_select") {
        setState("champ_select");
        send("game-phase-change", { phase: "champ_select" });
        if (!cachedRankedStats && client) {
          cachedRankedStats = await client.getCurrentRankedStats();
        }
        startChampSelectPolling();
      }
    } else if (phase === "InProgress" || phase === "GameStart") {
      if (state !== "game_start") {
        setState("game_start");
        send("game-phase-change", {
          phase: "in_game",
          pregameProb: lastPregameProb,
          pregameSummary: lastPregameSummary,
        });
        stopChampSelectPolling();
      }
    } else {
      if (state === "champ_select" || state === "game_start") {
        lastPregameProb = null;
        lastPregameSummary = null;
        send("game-phase-change", { phase: "none" });
      }
      setState("connected");
      stopChampSelectPolling();
    }
  };

  poll();
  gameflowTimer = setInterval(poll, GAMEFLOW_POLL_INTERVAL);
}

function stopChampSelectPolling(): void {
  if (champSelectTimer) { clearInterval(champSelectTimer); champSelectTimer = null; }
}

function startChampSelectPolling(): void {
  if (champSelectTimer) return;

  const poll = async () => {
    if (!client || state !== "champ_select") return;

    const session = await client.getChampSelectSession();
    if (!session) return;

    const anyPicked = [...session.myTeam, ...session.theirTeam].some((p) => p.championId > 0);
    if (!anyPicked) {
      send("champ-select-update", buildChampSelectUpdate(session, null));
      return;
    }

    const pregameModelType = "pregame";
    let probability: number | null = null;
    let topFactors: { feature: string; impact: number }[] = [];

    if (isModelLoaded(pregameModelType)) {
      try {
        const featureNamesList = getFeatureNames(pregameModelType);
        const features = buildPregameFeatures(session, cachedRankedStats, featureNamesList);
        probability = await predict(features, pregameModelType);
        lastPregameProb = probability;
        lastPregameSummary = getPregameSummaryFromFeatures(features);

        if (modelDir) {
          const shapValues = await computeShap(modelDir + "/pregame", features);
          if (shapValues) {
            topFactors = Object.entries(shapValues)
              .map(([feature, impact]) => ({ feature, impact }))
              .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
              .slice(0, 8);
          }
        }

        if (topFactors.length === 0) {
          topFactors = getFeatureImportance(pregameModelType)
            .slice(0, 8)
            .map((f) => ({ feature: f.feature, impact: f.importance }));
        }
      } catch (e) {
        logger.error("Pregame prediction failed:", e);
      }
    }

    send("champ-select-update", buildChampSelectUpdate(session, probability, topFactors));
  };

  poll();
  champSelectTimer = setInterval(poll, CHAMP_SELECT_POLL_INTERVAL);
}

function buildChampSelectUpdate(
  session: ChampSelectSession,
  probability: number | null,
  topFactors?: { feature: string; impact: number }[],
) {
  const localTeam = session.myTeam[0]?.team ?? 1;
  const isBlue = localTeam === 1;

  const mapPlayers = (players: ChampSelectSession["myTeam"], isMyTeam: boolean) =>
    players.map((p) => ({
      position: p.assignedPosition,
      championId: p.championId,
      championName: p.championId > 0 ? ddragon.getChampionName(p.championId) : "",
      isLocalPlayer: isMyTeam && isPlayerLocalByCell(p, session),
    }));

  return {
    phase: session.timer?.phase ?? "unknown",
    blue_win_probability: probability,
    blue_team: { players: mapPlayers(isBlue ? session.myTeam : session.theirTeam, isBlue) },
    red_team: { players: mapPlayers(isBlue ? session.theirTeam : session.myTeam, !isBlue) },
    is_blue_side: isBlue,
    timer_remaining: session.timer?.adjustedTimeLeftInPhase ?? 0,
    top_factors: topFactors ?? [],
    bans: {
      blue: isBlue ? (session.bans?.myTeamBans ?? []) : (session.bans?.theirTeamBans ?? []),
      red: isBlue ? (session.bans?.theirTeamBans ?? []) : (session.bans?.myTeamBans ?? []),
    },
  };
}

function isPlayerLocalByCell(
  player: ChampSelectSession["myTeam"][number],
  session: ChampSelectSession,
): boolean {
  const all = [...session.myTeam, ...session.theirTeam];
  return all.indexOf(player) === session.localPlayerCellId;
}

export function startLCUPolling(window: BrowserWindow, dir: string): void {
  stopLCUPolling();
  win = window;
  modelDir = dir;
  lastPregameProb = null;
  lastPregameSummary = null;

  stopLockfileWatch = watchLockfile((exists, creds) => {
    if (exists && creds) onConnected(creds);
    else onDisconnected();
  });

  startLockfilePolling();
}

export function stopLCUPolling(): void {
  stopAllTimers();
  stopLockfileWatch?.();
  stopLockfileWatch = null;
  client = null;
  state = "disconnected";
}

export function getLastPregameProb(): number | null {
  return lastPregameProb;
}

export function getLastPregameSummary(): Record<string, number> | null {
  return lastPregameSummary;
}

export function resetPregameState(): void {
  lastPregameProb = null;
  lastPregameSummary = null;
}
