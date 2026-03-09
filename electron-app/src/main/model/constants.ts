export const SNAPSHOT_SECONDS = [300, 600, 900, 1200, 1500, 1800, 2100, 2400, 2700, 3000];

export const LATE_GAME_SECONDS = 1800.0;
export const EARLY_GAME_WINDOW_SECONDS = 1500.0;

export const TIMELINE_FEATURE_NAMES = [
  "game_time_seconds",
  "blue_kills",
  "red_kills",
  "kill_diff",
  "blue_towers",
  "red_towers",
  "tower_diff",
  "blue_dragons",
  "red_dragons",
  "dragon_diff",
  "blue_barons",
  "red_barons",
  "blue_heralds",
  "red_heralds",
  "blue_inhibitors",
  "red_inhibitors",
  "blue_elder",
  "red_elder",
  "blue_cs",
  "red_cs",
  "cs_diff",
  "inhibitor_diff",
  "elder_diff",
  "first_blood_blue",
  "first_tower_blue",
  "first_dragon_blue",
];

const PREGAME_SUMMARY_COLS = [
  "avg_rank_diff",
  "rank_spread_diff",
  "avg_winrate_diff",
  "avg_mastery_diff",
  "melee_count_diff",
  "ad_ratio_diff",
  "total_games_diff",
  "hot_streak_count_diff",
  "veteran_count_diff",
  "mastery_level7_count_diff",
  "avg_champ_wr_diff",
  "scaling_score_diff",
  "max_scaling_score_diff",
  "stat_growth_diff",
  "scaling_tier_diff",
  "infinite_scaler_count_diff",
];

const SCALING_INTERACTION_COLS = [
  "scaling_advantage_realized",
  "early_game_window_closing",
];

const MOMENTUM_COLS = [
  "kill_diff_delta",
  "cs_diff_delta",
  "tower_diff_delta",
];

const TEMPORAL_COLS = [
  "kill_lead_erosion",
  "tower_lead_erosion",
  "kill_rate_diff",
  "cs_rate_diff",
  "dragon_rate_diff",
  "kill_diff_accel",
  "recent_kill_share_diff",
  "game_phase_early",
  "game_phase_mid",
  "game_phase_late",
  "objective_density",
];

const GOLD_ESTIMATION_COLS = [
  "blue_estimated_gold",
  "red_estimated_gold",
  "estimated_gold_diff",
];

const LEVEL_COLS = [
  "avg_level_diff",
  "max_level_diff",
];

const CHAMPION_SCALING_COLS = [
  "scaling_tier_x_time",
  "infinite_scaler_x_time",
];

export const LIVE_FEATURE_NAMES = [
  ...TIMELINE_FEATURE_NAMES,
  "pregame_blue_win_prob",
  ...PREGAME_SUMMARY_COLS,
  ...SCALING_INTERACTION_COLS,
  ...MOMENTUM_COLS,
  ...TEMPORAL_COLS,
  ...GOLD_ESTIMATION_COLS,
  ...LEVEL_COLS,
  ...CHAMPION_SCALING_COLS,
];
