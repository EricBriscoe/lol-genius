export interface StatusData {
  match_count: number;
  queue_stats: Record<string, number>;
  enrichment: { enriched: number; total: number };
  queue_depth: number;
}

export interface DistributionData {
  rank_distribution: Record<string, number>;
  patch_distribution: Record<string, number>;
  tier_seed_stats: Record<string, Record<string, number>>;
  match_age_range: { oldest: string; newest: string } | null;
}

export interface ModelRun {
  run_id: string;
  created_at: string;
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
  notes: string | null;
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

export interface CrawlerSSE {
  match_count: number;
  queue_depth: number;
  enrichment: { enriched: number; total: number };
  queue_stats: Record<string, number>;
}

export interface PredictLookup {
  found: boolean;
  error?: string;
  puuid?: string;
  game_name?: string;
  tag_line?: string;
  in_game: boolean;
  game_data?: unknown;
}

export interface PredictParticipant {
  puuid: string;
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
