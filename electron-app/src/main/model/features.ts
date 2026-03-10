import { SNAPSHOT_SECONDS, LIVE_FEATURE_NAMES, LATE_GAME_SECONDS, EARLY_GAME_WINDOW_SECONDS } from "./constants";

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
  blue_estimated_gold: number;
  red_estimated_gold: number;
  estimated_gold_diff: number;
  blue_avg_level: number;
  red_avg_level: number;
  blue_max_level: number;
  red_max_level: number;
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

  let blueKills = 0, redKills = 0, blueCs = 0, redCs = 0;
  let blueGold = 0, redGold = 0;
  const blueLevels: number[] = [];
  const redLevels: number[] = [];

  for (const player of allPlayers) {
    const team = player.team ?? "";
    const scores = player.scores ?? {};
    const kills = scores.kills ?? 0;
    const cs = scores.creepScore ?? scores.cs ?? 0;
    const level = player.level ?? 1;
    const itemGold = (player.items ?? []).reduce((sum, item) => sum + (item.price ?? 0), 0);
    if (team === "ORDER") {
      blueKills += kills;
      blueCs += cs;
      blueGold += itemGold;
      blueLevels.push(level);
    } else {
      redKills += kills;
      redCs += cs;
      redGold += itemGold;
      redLevels.push(level);
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
    blue_estimated_gold: blueGold,
    red_estimated_gold: redGold,
    estimated_gold_diff: blueGold - redGold,
    blue_avg_level: blueAvgLevel,
    red_avg_level: redAvgLevel,
    blue_max_level: blueMaxLevel,
    red_max_level: redMaxLevel,
  };
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
  pregameProb = 0.5,
  pregameSummary?: Record<string, number>,
): Record<string, number> {
  const rawGameTime = gameState.game_time;
  const gameTime = snapToSnapshot(rawGameTime);
  const killDiff = gameState.kill_diff;
  const csDiff = gameState.cs_diff;
  const towerDiff = gameState.tower_diff;
  const dragonDiff = gameState.dragon_diff;
  const gameMinutes = Math.max(rawGameTime / 60, 1);
  const timeNorm = rawGameTime / LATE_GAME_SECONDS;
  const scalingScoreDiff = pregameSummary?.scaling_score_diff ?? 0;

  const mapping: Record<string, number> = {
    game_time_seconds: gameTime,
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
    pregame_blue_win_prob: pregameProb,
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
    scaling_score_diff: scalingScoreDiff,
    max_scaling_score_diff: pregameSummary?.max_scaling_score_diff ?? 0,
    stat_growth_diff: pregameSummary?.stat_growth_diff ?? 0,
    scaling_tier_diff: pregameSummary?.scaling_tier_diff ?? 0,
    infinite_scaler_count_diff: pregameSummary?.infinite_scaler_count_diff ?? 0,
    scaling_advantage_realized: scalingScoreDiff * timeNorm,
    early_game_window_closing: scalingScoreDiff * Math.max(0, 1 - rawGameTime / EARLY_GAME_WINDOW_SECONDS),
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
    game_phase_early: rawGameTime <= 900 ? 1.0 : 0.0,
    game_phase_mid: rawGameTime > 900 && rawGameTime <= 1500 ? 1.0 : 0.0,
    game_phase_late: rawGameTime > 1500 ? 1.0 : 0.0,
    objective_density: (gameState.blue_dragons + gameState.red_dragons
      + gameState.blue_barons + gameState.red_barons
      + gameState.blue_heralds + gameState.red_heralds) / gameMinutes,
    blue_estimated_gold: gameState.blue_estimated_gold,
    red_estimated_gold: gameState.red_estimated_gold,
    estimated_gold_diff: gameState.estimated_gold_diff,
    avg_level_diff: gameState.blue_avg_level - gameState.red_avg_level,
    max_level_diff: gameState.blue_max_level - gameState.red_max_level,
    scaling_tier_x_time: (pregameSummary?.scaling_tier_diff ?? 0) * timeNorm,
    infinite_scaler_x_time: (pregameSummary?.infinite_scaler_count_diff ?? 0) * timeNorm,
  };

  const result: Record<string, number> = {};
  for (const col of LIVE_FEATURE_NAMES) {
    result[col] = mapping[col] ?? 0;
  }
  return result;
}
