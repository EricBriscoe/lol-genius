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
  top_factors?: PredictFactor[];
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

export interface LolGeniusAPI {
  onPredictionUpdate: (cb: (data: LiveGameUpdate) => void) => () => void;
  onConnectionStatus: (cb: (status: string) => void) => () => void;
  onAppUpdateStatus: (cb: (data: { status: string }) => void) => () => void;
  onChampSelectUpdate: (cb: (data: ChampSelectUpdate) => void) => () => void;
  onGamePhaseChange: (cb: (data: GamePhaseChange) => void) => () => void;
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
}

declare global {
  interface Window {
    lolGenius: LolGeniusAPI;
  }
}
