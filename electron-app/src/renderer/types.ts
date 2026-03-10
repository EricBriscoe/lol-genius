export interface LiveGameUpdate {
  game_time: number;
  blue_win_probability: number | null;
  kill_diff: number;
  dragon_diff: number;
  tower_diff: number;
  baron_diff: number;
  cs_diff: number;
  inhibitor_diff: number;
  elder_diff: number;
  game_reset?: boolean;
  status?: string;
  error?: string;
  top_factors?: PredictFactor[];
  pregame_ready?: boolean;
}

export interface PredictFactor {
  feature: string;
  impact: number;
}

export interface ModelInfo {
  version: string | null;
  featureCount: number;
  modelDir: string;
  polling: boolean;
  pregameVersion?: string | null;
  pregameFeatureCount?: number;
}

export interface DevLogEntry {
  timestamp: string;
  scope: string;
  level: string;
  message: string;
}

export interface ChampSelectPlayerInfo {
  position: string;
  championId: number;
  championName: string;
  championKey: string;
  isLocalPlayer: boolean;
}

export interface ChampSelectTeamInfo {
  players: ChampSelectPlayerInfo[];
}

export interface ChampSelectUpdate {
  phase: string;
  blue_win_probability: number | null;
  blue_team: ChampSelectTeamInfo;
  red_team: ChampSelectTeamInfo;
  is_blue_side: boolean;
  timer_remaining: number;
  ddragon_version: string;
  top_factors?: PredictFactor[];
  bans: { blue: number[]; red: number[] };
}

export interface GamePhaseChange {
  phase: "champ_select" | "in_game" | "none";
  pregameProb?: number;
  pregameSummary?: Record<string, number>;
}

export type AppUpdateEvent =
  | { status: "checking" }
  | { status: "available" }
  | { status: "not_available" }
  | { status: "downloading"; percent: number }
  | { status: "restarting" }
  | { status: "update_ready" }
  | { status: "error"; message: string }
  | { status: "model_updated" };

export interface PlayerIdentity {
  puuid: string;
  gameName: string;
  tagLine: string;
  summonerId: string;
}

export interface MatchHistoryResult {
  matches: MatchRow[];
  total: number;
  source: "cache" | "lcu";
  lcuOffline?: boolean;
}

export interface MatchRow {
  match_id: string;
  puuid: string;
  game_creation: number;
  game_duration: number | null;
  queue_id: number | null;
  champion_id: number | null;
  champion_name: string | null;
  team_position: string | null;
  win: number | null;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  cs: number | null;
  gold_earned: number | null;
  total_damage: number | null;
  vision_score: number | null;
  champion_level: number | null;
  total_damage_taken: number | null;
  item0: number | null;
  item1: number | null;
  item2: number | null;
  item3: number | null;
  item4: number | null;
  item5: number | null;
  item6: number | null;
  summoner_spell1: number | null;
  summoner_spell2: number | null;
  participants_json: string | null;
}

export interface RankedStatsRow {
  puuid: string;
  queue_type: string;
  tier: string | null;
  division: string | null;
  lp: number | null;
  wins: number | null;
  losses: number | null;
  updated_at: number;
}

export interface ChampionStatsAgg {
  champion_id: number;
  champion_name: string;
  games: number;
  wins: number;
  avg_kills: number;
  avg_deaths: number;
  avg_assists: number;
  avg_cs: number;
}

export interface LolGeniusAPI {
  onPredictionUpdate: (cb: (data: LiveGameUpdate) => void) => () => void;
  onConnectionStatus: (cb: (status: string) => void) => () => void;
  onAppUpdateStatus: (cb: (data: AppUpdateEvent) => void) => () => void;
  onChampSelectUpdate: (cb: (data: ChampSelectUpdate) => void) => () => void;
  onGamePhaseChange: (cb: (data: GamePhaseChange) => void) => () => void;
  onPlayerIdentity: (cb: (data: PlayerIdentity) => void) => () => void;
  onPlayerDataUpdate: (cb: (data: { newMatches: number }) => void) => () => void;
  startPolling: () => Promise<void>;
  stopPolling: () => Promise<void>;
  getModelInfo: () => Promise<ModelInfo>;
  checkForUpdates: () => Promise<boolean>;
  setDevMode: (enabled: boolean) => Promise<void>;
  getDevMode: () => Promise<boolean>;
  onDevLog: (cb: (entry: DevLogEntry) => void) => () => void;
  getAppVersion: () => Promise<string>;
  setAlwaysOnTop: (enabled: boolean) => Promise<void>;
  getAlwaysOnTop: () => Promise<boolean>;
  getPlayerIdentity: () => Promise<PlayerIdentity | null>;
  getMatchHistory: (params: { offset: number; limit: number; championId?: number; queueId?: number }) => Promise<MatchHistoryResult>;
  getChampionStats: () => Promise<ChampionStatsAgg[]>;
  getRankedStats: () => Promise<RankedStatsRow[]>;
  refreshPlayerData: () => Promise<void>;
  forceRestart: () => Promise<void>;
}

declare global {
  interface Window {
    lolGenius: LolGeniusAPI;
  }
}
