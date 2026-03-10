import { SNAPSHOT_SECONDS, LIVE_FEATURE_NAMES } from "./constants";
import featureSpec from "@shared/live-feature-names.json";

interface AllGameData {
  allPlayers?: Player[];
  events?: { Events?: GameEvent[] };
  gameData?: { gameTime?: number; gameId?: number };
}

interface ItemData {
  itemID?: number;
  price?: number;
}

interface Player {
  summonerName?: string;
  riotId?: string;
  team?: string;
  scores?: { kills?: number; creepScore?: number; cs?: number };
  items?: ItemData[];
  level?: number;
  position?: string;
}

interface GameEvent {
  EventName?: string;
  KillerName?: string;
  DragonType?: string;
}

export interface GameState {
  game_time: number;
  blue_kills: number;
  red_kills: number;
  kill_diff: number;
  blue_cs: number;
  red_cs: number;
  cs_diff: number;
  blue_dragons: number;
  red_dragons: number;
  dragon_diff: number;
  blue_barons: number;
  red_barons: number;
  baron_diff: number;
  blue_towers: number;
  red_towers: number;
  tower_diff: number;
  blue_heralds: number;
  red_heralds: number;
  blue_inhibitors: number;
  red_inhibitors: number;
  inhibitor_diff: number;
  blue_elder: number;
  red_elder: number;
  elder_diff: number;
  first_blood_blue: number;
  first_tower_blue: number;
  first_dragon_blue: number;
  blue_avg_level: number;
  red_avg_level: number;
  blue_max_level: number;
  red_max_level: number;
  [key: `${"blue" | "red"}_${"top" | "jg" | "mid" | "bot" | "sup"}_${"cs" | "level" | "kills"}`]: number;
}

function getPlayerTeam(allPlayers: Player[], name: string): string {
  for (const player of allPlayers) {
    if (player.summonerName === name || player.riotId === name) {
      return player.team ?? "";
    }
  }
  return "";
}

export function parseLiveClientData(data: AllGameData): GameState {
  const allPlayers = data.allPlayers ?? [];
  const events = data.events?.Events ?? [];
  const gameTime = data.gameData?.gameTime ?? 0;

  const POSITION_ABBREV: Record<string, string> = {
    TOP: "top", JUNGLE: "jg", MIDDLE: "mid", BOTTOM: "bot", UTILITY: "sup",
  };

  let blueKills = 0, redKills = 0, blueCs = 0, redCs = 0;
  const blueLevels: number[] = [];
  const redLevels: number[] = [];
  const perRole: Record<string, number> = {};

  for (const player of allPlayers) {
    const team = player.team ?? "";
    const scores = player.scores ?? {};
    const kills = scores.kills ?? 0;
    const cs = scores.creepScore ?? scores.cs ?? 0;
    const level = player.level ?? 1;
    const side = team === "ORDER" ? "blue" : "red";
    const pos = POSITION_ABBREV[player.position ?? ""];
    if (team === "ORDER") {
      blueKills += kills;
      blueCs += cs;
      blueLevels.push(level);
    } else {
      redKills += kills;
      redCs += cs;
      redLevels.push(level);
    }
    if (pos) {
      perRole[`${side}_${pos}_cs`] = cs;
      perRole[`${side}_${pos}_level`] = level;
      perRole[`${side}_${pos}_kills`] = kills;
    }
  }

  const blueAvgLevel = blueLevels.length > 0 ? blueLevels.reduce((a, b) => a + b, 0) / blueLevels.length : 1.0;
  const redAvgLevel = redLevels.length > 0 ? redLevels.reduce((a, b) => a + b, 0) / redLevels.length : 1.0;
  const blueMaxLevel = blueLevels.length > 0 ? Math.max(...blueLevels) : 1;
  const redMaxLevel = redLevels.length > 0 ? Math.max(...redLevels) : 1;

  let blueDragons = 0, redDragons = 0, blueBarons = 0, redBarons = 0;
  let blueTowers = 0, redTowers = 0, blueHeralds = 0, redHeralds = 0;
  let blueInhibitors = 0, redInhibitors = 0, blueElder = 0, redElder = 0;
  let firstBloodBlue = 0, firstTowerBlue = 0, firstDragonBlue = 0;
  let firstBloodSet = false, firstTowerSet = false, firstDragonSet = false;

  for (const event of events) {
    const name = event.EventName ?? "";
    const killer = event.KillerName ?? "";

    if (name === "FirstBlood") {
      if (!firstBloodSet) {
        firstBloodSet = true;
        firstBloodBlue = getPlayerTeam(allPlayers, killer) === "ORDER" ? 1 : 0;
      }
    } else if (name === "DragonKill") {
      const killerTeam = getPlayerTeam(allPlayers, killer);
      if (event.DragonType === "Elder") {
        if (killerTeam === "ORDER") blueElder++;
        else redElder++;
      } else {
        if (killerTeam === "ORDER") {
          blueDragons++;
          if (!firstDragonSet) { firstDragonSet = true; firstDragonBlue = 1; }
        } else {
          redDragons++;
          if (!firstDragonSet) { firstDragonSet = true; firstDragonBlue = 0; }
        }
      }
    } else if (name === "BaronKill") {
      if (getPlayerTeam(allPlayers, killer) === "ORDER") blueBarons++;
      else redBarons++;
    } else if (name === "HeraldKill") {
      if (getPlayerTeam(allPlayers, killer) === "ORDER") blueHeralds++;
      else redHeralds++;
    } else if (name === "TurretKilled") {
      const killerTeam = getPlayerTeam(allPlayers, killer);
      if (killerTeam === "ORDER") {
        blueTowers++;
        if (!firstTowerSet) { firstTowerSet = true; firstTowerBlue = 1; }
      } else {
        redTowers++;
        if (!firstTowerSet) { firstTowerSet = true; firstTowerBlue = 0; }
      }
    } else if (name === "InhibitorKilled") {
      if (getPlayerTeam(allPlayers, killer) === "ORDER") blueInhibitors++;
      else redInhibitors++;
    }
  }

  return {
    game_time: gameTime,
    blue_kills: blueKills, red_kills: redKills, kill_diff: blueKills - redKills,
    blue_cs: blueCs, red_cs: redCs, cs_diff: blueCs - redCs,
    blue_dragons: blueDragons, red_dragons: redDragons, dragon_diff: blueDragons - redDragons,
    blue_barons: blueBarons, red_barons: redBarons, baron_diff: blueBarons - redBarons,
    blue_towers: blueTowers, red_towers: redTowers, tower_diff: blueTowers - redTowers,
    blue_heralds: blueHeralds, red_heralds: redHeralds,
    blue_inhibitors: blueInhibitors, red_inhibitors: redInhibitors,
    inhibitor_diff: blueInhibitors - redInhibitors,
    blue_elder: blueElder, red_elder: redElder, elder_diff: blueElder - redElder,
    first_blood_blue: firstBloodBlue,
    first_tower_blue: firstTowerBlue,
    first_dragon_blue: firstDragonBlue,
    blue_avg_level: blueAvgLevel,
    red_avg_level: redAvgLevel,
    blue_max_level: blueMaxLevel,
    red_max_level: redMaxLevel,
    ...perRole,
  } as GameState;
}

export function snapToSnapshot(gameTime: number): number {
  let best = SNAPSHOT_SECONDS[0];
  let bestDist = Math.abs(gameTime - best);
  for (const t of SNAPSHOT_SECONDS) {
    const dist = Math.abs(gameTime - t);
    if (dist < bestDist) { best = t; bestDist = dist; }
  }
  return best;
}

export interface MomentumState {
  prevDiffs: { kill_diff: number; cs_diff: number; tower_diff: number } | null;
  peakKillDiff: number;
  peakTowerDiff: number;
  killDiffAccel: number;
  recentKillShareDiff: number;
}

export function buildLiveFeatures(
  gameState: GameState,
  momentum: MomentumState,
  pregameSummary?: Record<string, number>,
): Record<string, number> {
  const rawGameTime = gameState.game_time;
  const killDiff = gameState.kill_diff;
  const csDiff = gameState.cs_diff;
  const towerDiff = gameState.tower_diff;
  const dragonDiff = gameState.dragon_diff;
  const gameMinutes = Math.max(rawGameTime / 60, 1);

  const mapping: Record<string, number> = {
    game_time_seconds: rawGameTime,
    blue_kills: gameState.blue_kills,
    red_kills: gameState.red_kills,
    kill_diff: killDiff,
    blue_cs: gameState.blue_cs,
    red_cs: gameState.red_cs,
    blue_towers: gameState.blue_towers,
    red_towers: gameState.red_towers,
    tower_diff: towerDiff,
    blue_dragons: gameState.blue_dragons,
    red_dragons: gameState.red_dragons,
    dragon_diff: dragonDiff,
    blue_barons: gameState.blue_barons,
    red_barons: gameState.red_barons,
    blue_heralds: gameState.blue_heralds,
    red_heralds: gameState.red_heralds,
    blue_inhibitors: gameState.blue_inhibitors,
    red_inhibitors: gameState.red_inhibitors,
    blue_elder: gameState.blue_elder,
    red_elder: gameState.red_elder,
    cs_diff: csDiff,
    inhibitor_diff: gameState.inhibitor_diff,
    elder_diff: gameState.elder_diff,
    first_blood_blue: gameState.first_blood_blue,
    first_tower_blue: gameState.first_tower_blue,
    first_dragon_blue: gameState.first_dragon_blue,
    avg_rank_diff: pregameSummary?.avg_rank_diff ?? 0,
    rank_spread_diff: pregameSummary?.rank_spread_diff ?? 0,
    avg_winrate_diff: pregameSummary?.avg_winrate_diff ?? 0,
    avg_mastery_diff: pregameSummary?.avg_mastery_diff ?? 0,
    melee_count_diff: pregameSummary?.melee_count_diff ?? 0,
    ad_ratio_diff: pregameSummary?.ad_ratio_diff ?? 0,
    total_games_diff: pregameSummary?.total_games_diff ?? 0,
    hot_streak_count_diff: pregameSummary?.hot_streak_count_diff ?? 0,
    veteran_count_diff: pregameSummary?.veteran_count_diff ?? 0,
    mastery_level7_count_diff: pregameSummary?.mastery_level7_count_diff ?? 0,
    avg_champ_wr_diff: pregameSummary?.avg_champ_wr_diff ?? 0,
    scaling_score_diff: pregameSummary?.scaling_score_diff ?? 0,
    stat_growth_diff: pregameSummary?.stat_growth_diff ?? 0,
    infinite_scaler_count_diff: pregameSummary?.infinite_scaler_count_diff ?? 0,
    kill_diff_delta: momentum.prevDiffs
      ? killDiff - momentum.prevDiffs.kill_diff : 0,
    cs_diff_delta: momentum.prevDiffs
      ? csDiff - momentum.prevDiffs.cs_diff : 0,
    tower_diff_delta: momentum.prevDiffs
      ? towerDiff - momentum.prevDiffs.tower_diff : 0,
    kill_lead_erosion: Math.max(momentum.peakKillDiff, killDiff) - killDiff,
    tower_lead_erosion: Math.max(momentum.peakTowerDiff, towerDiff) - towerDiff,
    kill_rate_diff: killDiff / gameMinutes,
    cs_rate_diff: csDiff / gameMinutes,
    dragon_rate_diff: dragonDiff / gameMinutes,
    kill_diff_accel: momentum.killDiffAccel,
    recent_kill_share_diff: momentum.recentKillShareDiff,
    objective_density: (gameState.blue_dragons + gameState.red_dragons
      + gameState.blue_barons + gameState.red_barons
      + gameState.blue_heralds + gameState.red_heralds) / gameMinutes,
    avg_level_diff: gameState.blue_avg_level - gameState.red_avg_level,
    max_level_diff: gameState.blue_max_level - gameState.red_max_level,
    blue_has_soul: gameState.blue_dragons >= 4 ? 1.0 : 0.0,
    red_has_soul: gameState.red_dragons >= 4 ? 1.0 : 0.0,
    blue_soul_point: gameState.blue_dragons >= 3 ? 1.0 : 0.0,
    red_soul_point: gameState.red_dragons >= 3 ? 1.0 : 0.0,
  };

  for (const pos of featureSpec.positions) {
    const gs = gameState as Record<string, number>;
    mapping[`${pos}_cs_diff`] = (gs[`blue_${pos}_cs`] ?? 0) - (gs[`red_${pos}_cs`] ?? 0);
    mapping[`${pos}_level_diff`] = (gs[`blue_${pos}_level`] ?? 1) - (gs[`red_${pos}_level`] ?? 1);
    mapping[`${pos}_kill_diff`] = (gs[`blue_${pos}_kills`] ?? 0) - (gs[`red_${pos}_kills`] ?? 0);
  }

  const result: Record<string, number> = {};
  for (const col of LIVE_FEATURE_NAMES) {
    result[col] = mapping[col] ?? 0;
  }
  return result;
}
