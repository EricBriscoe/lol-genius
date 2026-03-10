import { BrowserWindow } from "electron";
import { findLockfile, readLockfile, watchLockfile } from "./lockfile";
import { createLCUClient, type LCUClient } from "./api";
import type { LCUCredentials, ChampSelectSession, ChampSelectPlayer, RankedStats, GameflowSession } from "./types";
import { buildPregameFeatures, getPregameSummaryFromFeatures } from "../model/pregame-features";
import { predict, isModelLoaded, getFeatureNames } from "../model/inference";
import { computeTopFactors } from "../model/shap-factors";
import { getModelDir } from "../updater";
import { safeSend } from "../ipc";
import { setPregameData, startPolling as startLivePolling, stopPolling as stopLivePolling } from "../live-client/poller";
import { onLCUConnected, onLCUDisconnected } from "../player-data/index";
import * as ddragon from "../model/ddragon";
import log from "../log";
import { clearTimer } from "../timers";

const logger = log.scope("lcu-poller");

export type LCUState = "disconnected" | "connected" | "champ_select" | "game_start";

export function getGamePhase(): LCUState { return state; }

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
let liveModelDir: string | null = null;
let lastPregameSummary: Record<string, number> | null = null;
let lastPregameProb: number | null = null;
let cachedRankedStats: RankedStats | null = null;

function send(channel: string, data: unknown): void {
  safeSend(win, channel, data);
}

function setState(next: LCUState): void {
  if (state === next) return;
  logger.debug("LCU state:", state, "→", next);
  state = next;
}

function stopAllTimers(): void {
  lockfilePollTimer = clearTimer(lockfilePollTimer);
  gameflowTimer = clearTimer(gameflowTimer);
  champSelectTimer = clearTimer(champSelectTimer);
}

function onDisconnected(): void {
  stopAllTimers();
  client = null;
  cachedRankedStats = null;
  setState("disconnected");
  send("connection-status", "lcu_disconnected");
  onLCUDisconnected();
  startLockfilePolling();
}

function onConnected(creds: LCUCredentials): void {
  stopAllTimers();
  client = createLCUClient(creds);
  setState("connected");
  send("connection-status", "lcu_connected");
  onLCUConnected(client);
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
        stopChampSelectPolling();

        if (lastPregameSummary === null && client && isModelLoaded("pregame")) {
          try {
            const gfSession = await client.getGameflowSession();
            if (gfSession) {
              const champSession = gameflowToChampSelect(gfSession);
              const featureNamesList = getFeatureNames("pregame");
              const features = buildPregameFeatures(champSession, null, featureNamesList);
              lastPregameProb = await predict(features, "pregame");
              lastPregameSummary = getPregameSummaryFromFeatures(features);
            }
          } catch (e) {
            logger.error("Mid-game pregame prediction failed:", e);
          }
        }

        setPregameData(lastPregameSummary);
        send("game-phase-change", {
          phase: "in_game",
          pregameProb: lastPregameProb,
          pregameSummary: lastPregameSummary,
        });

        if (win && liveModelDir) {
          startLivePolling(win, liveModelDir);
        }
      }
    } else {
      if (state === "champ_select" || state === "game_start") {
        if (state === "game_start") stopLivePolling();
        lastPregameSummary = null;
        lastPregameProb = null;
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
  champSelectTimer = clearTimer(champSelectTimer);
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

    let probability: number | null = null;
    let factorAnalysis: import("../../renderer/types").FactorAnalysis | undefined;

    if (isModelLoaded("pregame")) {
      try {
        const featureNamesList = getFeatureNames("pregame");
        const features = buildPregameFeatures(session, cachedRankedStats, featureNamesList);
        probability = await predict(features, "pregame");
        lastPregameProb = probability;
        lastPregameSummary = getPregameSummaryFromFeatures(features);

        factorAnalysis = await computeTopFactors(getModelDir("pregame"), features, "pregame");
      } catch (e) {
        logger.error("Pregame prediction failed:", e);
      }
    }

    send("champ-select-update", buildChampSelectUpdate(session, probability, factorAnalysis));
  };

  poll();
  champSelectTimer = setInterval(poll, CHAMP_SELECT_POLL_INTERVAL);
}

function buildChampSelectUpdate(
  session: ChampSelectSession,
  probability: number | null,
  factorAnalysis?: import("../../renderer/types").FactorAnalysis,
) {
  const localTeam = session.myTeam[0]?.team ?? 1;
  const isBlue = localTeam === 1;

  const mapPlayers = (players: ChampSelectSession["myTeam"], isMyTeam: boolean) =>
    players.map((p) => ({
      position: p.assignedPosition,
      championId: p.championId,
      championName: p.championId > 0 ? ddragon.getChampionName(p.championId) : "",
      championKey: p.championId > 0 ? ddragon.getChampionInternalName(p.championId) : "",
      isLocalPlayer: isMyTeam && isPlayerLocalByCell(p, session),
    }));

  return {
    phase: session.timer?.phase ?? "unknown",
    blue_win_probability: probability,
    blue_team: { players: mapPlayers(isBlue ? session.myTeam : session.theirTeam, isBlue) },
    red_team: { players: mapPlayers(isBlue ? session.theirTeam : session.myTeam, !isBlue) },
    is_blue_side: isBlue,
    timer_remaining: session.timer?.adjustedTimeLeftInPhase ?? 0,
    ddragon_version: ddragon.getChampionVersion(),
    factor_analysis: factorAnalysis,
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

function gameflowToChampSelect(gf: GameflowSession): ChampSelectSession {
  const map = (players: GameflowSession["gameData"]["teamOne"]): ChampSelectPlayer[] =>
    players.map((p) => ({
      summonerId: p.summonerId,
      championId: p.championId,
      assignedPosition: p.selectedPosition,
      spell1Id: p.spell1Id,
      spell2Id: p.spell2Id,
      team: p.team,
    }));

  return {
    myTeam: map(gf.gameData.teamOne),
    theirTeam: map(gf.gameData.teamTwo),
    bans: { myTeamBans: [], theirTeamBans: [] },
    timer: { phase: "GAME_STARTING", adjustedTimeLeftInPhase: 0 },
    localPlayerCellId: -1,
  };
}

export function startLCUPolling(window: BrowserWindow, modelDir: string): void {
  stopLCUPolling();
  win = window;
  liveModelDir = modelDir;
  lastPregameSummary = null;
  lastPregameProb = null;

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

