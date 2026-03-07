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
}

export interface LolGeniusAPI {
  onPredictionUpdate: (cb: (data: LiveGameUpdate) => void) => () => void;
  onConnectionStatus: (cb: (status: string) => void) => () => void;
  onAppUpdateStatus: (cb: (data: { status: string }) => void) => () => void;
  startPolling: () => Promise<void>;
  stopPolling: () => Promise<void>;
  getModelInfo: () => Promise<ModelInfo>;
  checkForUpdates: () => Promise<boolean>;
}

declare global {
  interface Window {
    lolGenius: LolGeniusAPI;
  }
}
