export const SNAPSHOT_SECONDS = [300, 600, 900, 1200, 1500, 1800, 2100, 2400, 2700, 3000];

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
  "stat_growth_diff",
  "infinite_scaler_count_diff",
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
  "objective_density",
];

const LEVEL_COLS = [
  "avg_level_diff",
  "max_level_diff",
];

const DRAGON_SOUL_COLS = [
  "blue_has_soul",
  "red_has_soul",
  "blue_soul_point",
  "red_soul_point",
];

const POSITIONS = ["top", "jg", "mid", "bot", "sup"] as const;
const STATS = ["cs", "level", "kill"] as const;
const PER_ROLE_COLS = POSITIONS.flatMap(
  (pos) => STATS.map((stat) => `${pos}_${stat}_diff`),
);

export const LIVE_FEATURE_NAMES = [
  ...TIMELINE_FEATURE_NAMES,
  ...PREGAME_SUMMARY_COLS,
  ...MOMENTUM_COLS,
  ...TEMPORAL_COLS,
  ...LEVEL_COLS,
  ...DRAGON_SOUL_COLS,
  ...PER_ROLE_COLS,
];
