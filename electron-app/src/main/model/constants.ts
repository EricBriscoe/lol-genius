import featureSpec from "@shared/live-feature-names.json";

export const SNAPSHOT_SECONDS = featureSpec.snapshot_seconds;

const GOLD_COLS = new Set(featureSpec.gold_cols);

export const TIMELINE_FEATURE_NAMES = featureSpec.timeline_feature_names.filter(
  (f: string) => !GOLD_COLS.has(f),
);

export const LIVE_FEATURE_NAMES = [
  ...TIMELINE_FEATURE_NAMES,
  ...featureSpec.pregame_summary_cols,
  ...featureSpec.momentum_cols,
  ...featureSpec.temporal_cols,
  ...featureSpec.level_cols,
  ...featureSpec.dragon_soul_cols,
  ...featureSpec.positions.flatMap(
    (pos: string) => featureSpec.per_role_stats.map((stat: string) => `${pos}_${stat}_diff`),
  ),
];
