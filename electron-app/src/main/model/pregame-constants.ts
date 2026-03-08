export const POSITION_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"] as const;

export const POSITION_SHORT: Record<string, string> = {
  TOP: "top",
  JUNGLE: "jg",
  MIDDLE: "mid",
  BOTTOM: "bot",
  UTILITY: "sup",
};

export const TIER_MAP: Record<string, number> = {
  IRON: 0,
  BRONZE: 4,
  SILVER: 8,
  GOLD: 12,
  PLATINUM: 16,
  EMERALD: 20,
  DIAMOND: 24,
  MASTER: 28,
  GRANDMASTER: 29,
  CHALLENGER: 30,
};

export const DIV_MAP: Record<string, number> = { IV: 0, III: 1, II: 2, I: 3 };

export const FLASH_ID = 4;

export const SPELL_MAP: Record<number, string> = {
  14: "has_ignite",
  12: "has_teleport",
  11: "has_smite",
  3: "has_exhaust",
  7: "has_heal",
  21: "has_barrier",
  6: "has_ghost",
  1: "has_cleanse",
};

export const ALL_TAGS = ["Fighter", "Mage", "Assassin", "Tank", "Marksman", "Support"] as const;

export const TAG_ADVANTAGE: Record<string, number> = {
  "Assassin:Mage": 0.6,
  "Tank:Assassin": 0.4,
  "Fighter:Tank": 0.3,
  "Marksman:Assassin": -0.5,
  "Mage:Fighter": 0.3,
  "Support:Assassin": -0.3,
};

export const DEFAULT_PLAYER_FEATURES: Record<string, number> = {
  rank_numeric: 12.0,
  league_points: 0.0,
  ranked_winrate: 0.5,
  ranked_games: 0.0,
  hot_streak: 0.0,
  fresh_blood: 0.0,
  veteran: 0.0,
  recent_winrate: 0.5,
  recent_games: 0.0,
  avg_kda: 2.0,
  avg_cs_per_min: 6.0,
  avg_vision: 20.0,
  avg_damage_share: 0.2,
  avg_wards_placed: 0.0,
  avg_wards_killed: 0.0,
  avg_damage_taken: 0.0,
  avg_gold_spent: 0.0,
  avg_cc_score: 0.0,
  avg_heal_total: 0.0,
  avg_magic_dmg_share: 0.0,
  avg_phys_dmg_share: 0.0,
  avg_multikill_rate: 0.0,
  kda_variance: 0.0,
  kda_skewness: 0.0,
  champ_winrate: 0.5,
  champ_games: 0.0,
  champ_global_wr: 0.5,
  mastery_points: 0.0,
  mastery_points_log: 0.0,
  mastery_above_12k: 0.0,
  mastery_level: 0.0,
  days_since_champ_played: 30.0,
  is_autofill: 0.0,
  role_experience_ratio: 0.0,
  summoner_level: 0.0,
  winrate_rank_residual: 0.0,
  games_per_level: 0.0,
  rank_per_game: 0.0,
  level_rank_mismatch: 0.0,
  smurf_score: 0.0,
  loss_streak: 0.0,
  avg_time_between_games_hrs: 24.0,
  games_last_24h: 0.0,
  flash_on_d: 0.0,
  has_ignite: 0.0,
  has_teleport: 0.0,
  has_smite: 0.0,
  has_exhaust: 0.0,
  has_heal: 0.0,
  has_barrier: 0.0,
  has_ghost: 0.0,
  has_cleanse: 0.0,
};

export const SMURF_WR_RESIDUAL_WEIGHT = 2.0;
export const SMURF_RANK_MISMATCH_WEIGHT = 0.5;
export const SMURF_GAMES_PER_LEVEL_WEIGHT = 1.5;
export const SMURF_RANK_PER_GAME_WEIGHT = 1.0;
