import { describe, it, expect } from "vitest";
import { LIVE_FEATURE_NAMES, SNAPSHOT_SECONDS, TIMELINE_FEATURE_NAMES } from "./constants";
import featureSpec from "@shared/live-feature-names.json";
import shapConfig from "@shared/shap-categories.json";

function composeLiveFeatures(): string[] {
  const goldCols = new Set(featureSpec.gold_cols);
  const perRole = featureSpec.positions.flatMap(
    (pos: string) => featureSpec.per_role_stats.map((stat: string) => `${pos}_${stat}_diff`),
  );
  return [
    ...featureSpec.timeline_feature_names.filter((f: string) => !goldCols.has(f)),
    ...featureSpec.pregame_summary_cols,
    ...featureSpec.momentum_cols,
    ...featureSpec.temporal_cols,
    ...featureSpec.level_cols,
    ...featureSpec.dragon_soul_cols,
    ...perRole,
  ];
}

describe("shared feature names JSON", () => {
  it("SNAPSHOT_SECONDS matches JSON", () => {
    expect(SNAPSHOT_SECONDS).toEqual(featureSpec.snapshot_seconds);
  });

  it("TIMELINE_FEATURE_NAMES excludes gold cols", () => {
    const goldCols = new Set(featureSpec.gold_cols);
    for (const f of TIMELINE_FEATURE_NAMES) {
      expect(goldCols.has(f)).toBe(false);
    }
  });

  it("LIVE_FEATURE_NAMES exact ordered match with JSON composition", () => {
    expect(LIVE_FEATURE_NAMES).toEqual(composeLiveFeatures());
  });

  it("LIVE_FEATURE_NAMES has expected count", () => {
    expect(LIVE_FEATURE_NAMES.length).toBe(72);
  });
});

describe("shared SHAP categories JSON", () => {
  it("live_category_map values match JSON exactly", () => {
    expect(shapConfig.live_category_map).toEqual(shapConfig.live_category_map);
  });

  it("all live category features exist in LIVE_FEATURE_NAMES", () => {
    const liveSet = new Set(LIVE_FEATURE_NAMES);
    for (const [cat, features] of Object.entries(shapConfig.live_category_map)) {
      for (const feat of features as string[]) {
        expect(liveSet.has(feat), `Feature '${feat}' in category '${cat}' not in LIVE_FEATURE_NAMES`).toBe(true);
      }
    }
  });

  it("every live feature has a SHAP category or is excluded", () => {
    const categorized = new Set<string>();
    for (const features of Object.values(shapConfig.live_category_map)) {
      for (const f of features as string[]) categorized.add(f);
    }
    const excluded = new Set(shapConfig.excluded_features);
    for (const feat of LIVE_FEATURE_NAMES) {
      expect(
        categorized.has(feat) || excluded.has(feat),
        `Feature '${feat}' has no SHAP category and is not excluded`,
      ).toBe(true);
    }
  });

  it("has required config keys", () => {
    expect(shapConfig.impact_threshold).toBe(0.3);
    expect(shapConfig.max_groups).toBe(5);
    expect(shapConfig.narrative_config.strong_threshold).toBe(5);
    expect(shapConfig.narrative_config.moderate_threshold).toBe(2);
  });
});
