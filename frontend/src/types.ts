interface BaseStatus {
  match_count: number;
  queue_stats: Record<string, number>;
  enrichment: { enriched: number; total: number };
  timeline: { fetched: number; total: number };
  queue_depth: number;
}

export interface StatusData extends BaseStatus {}


export interface DistributionData {
  rank_distribution: Record<string, number>;
  patch_distribution: Record<string, number>;
  tier_seed_stats: Record<string, Record<string, number>>;
  match_age_range: { oldest: string; newest: string } | null;
  crawl_rate: { hour: string; count: number }[];
}

export interface ModelRun {
  run_id: string;
  created_at: string;
  model_type: "pregame" | "live";
  total_matches: number;
  train_count: number;
  test_count: number;
  feature_count: number;
  patch_min: string;
  patch_max: string;
  target_mean: number;
  hyperparameters: Record<string, number | string> | null;
  best_iteration: number | null;
  best_train_score: number | null;
  training_seconds: number | null;
  accuracy: number | null;
  auc_roc: number | null;
  log_loss: number | null;
  tn: number | null;
  fp: number | null;
  fn: number | null;
  tp: number | null;
  top_features: { name: string; importance: number }[] | null;
  time_window_metrics: { minutes: number; accuracy: number; auc_roc: number | null; count: number }[] | null;
  notes: string | null;
}

export interface TrainingRequest {
  notes?: string;
  preset?: string;
  params?: Record<string, number | string>;
  auto_tune?: boolean;
  model_type?: "pregame" | "live";
}

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

export interface LiveGameStatus {
  connected: boolean;
  host: string | null;
  port: number | null;
  status?: string;
  pregame_win_prob?: number | null;
  current: LiveGameUpdate | null;
  history: { game_time: number; probability: number }[];
}

export interface TrainingStatus {
  stage: string;
  run_id?: string;
  matches?: number;
  features?: number;
  error?: string;
  metrics?: Record<string, number>;
  started_at?: number;
  completed_at?: number;
}

export interface CrawlerSSE extends BaseStatus {}

export interface SpectatorGameData {
  gameId: number;
  gameMode: string;
  gameLength: number;
  participants: {
    puuid: string;
    teamId: number;
    championId: number;
    spell1Id: number;
    spell2Id: number;
  }[];
  bannedChampions: { championId: number; teamId: number; pickTurn: number }[];
}

export interface PredictLookup {
  found: boolean;
  error?: string;
  puuid?: string;
  game_name?: string;
  tag_line?: string;
  in_game: boolean;
  game_data?: SpectatorGameData;
}

export interface PredictParticipant {
  puuid: string;
  riot_id: string;
  game_name: string;
  tag_line: string;
  champion_id: number;
  champion_name: string;
  team_id: number;
  position: string;
  rank: {
    tier: string;
    rank: string;
    league_points: number;
    wins: number;
    losses: number;
  } | null;
  summoner_level: number;
}

export interface PredictFactor {
  feature: string;
  impact: number;
}

export interface PredictResult {
  blue_win_probability: number;
  top_factors: PredictFactor[];
  participants: PredictParticipant[];
  bans: { champion_id: number; champion_name: string; team_id: number }[];
  game_id: number;
  game_mode: string;
  game_length_seconds: number;
}

export interface ChampionStat {
  champion_id: number;
  champion_name: string;
  games: number;
  wins: number;
  winrate: number;
  pick_rate: number;
  ban_rate: number;
  bans: number;
  avg_kills: number;
  avg_deaths: number;
  avg_assists: number;
  avg_cs: number;
  avg_gold: number;
  avg_damage: number;
  avg_vision: number;
  positions: Record<string, number>;
  tags: string[];
  attack_range: number;
}

export interface ChampionStatsResponse {
  total_matches: number;
  patch: string | null;
  available_patches: string[];
  tier: string | null;
  available_tiers: string[];
  champions: ChampionStat[];
}

export function isCrawlerSSE(data: unknown): data is CrawlerSSE {
  return typeof data === "object" && data !== null && "match_count" in data;
}

export function isTrainingStatus(data: unknown): data is TrainingStatus {
  return typeof data === "object" && data !== null && "stage" in data;
}

export function isLiveGameUpdate(data: unknown): data is LiveGameUpdate {
  return typeof data === "object" && data !== null && "blue_win_probability" in data;
}
