import type { GroupedFactor, FactorAnalysis } from "../../renderer/types";
import shapConfig from "@shared/shap-categories.json";

const LIVE_CATEGORY_MAP: Record<string, string[]> = shapConfig.live_category_map;

const PREGAME_SUFFIX_RULES: [string, string[]][] = shapConfig.pregame_suffix_rules as [string, string[]][];

const PREGAME_EXACT: Record<string, string> = shapConfig.pregame_exact;

const EXCLUDED = new Set(shapConfig.excluded_features);
const IMPACT_THRESHOLD = shapConfig.impact_threshold;
const MAX_GROUPS = shapConfig.max_groups;
const NARR = shapConfig.narrative_config;

function sigmoid(x: number): number {
  return 1 / (1 + Math.exp(-x));
}

function buildLiveFeatureMap(): Map<string, string> {
  const m = new Map<string, string>();
  for (const [cat, features] of Object.entries(LIVE_CATEGORY_MAP)) {
    for (const f of features) m.set(f, cat);
  }
  return m;
}

function classifyPregameFeature(name: string): string | null {
  const bare = name.replace(/^(blue|red)_[a-z]{2,3}_/, "").replace(/^(blue|red)_/, "");
  if (PREGAME_EXACT[bare]) return PREGAME_EXACT[bare];
  for (const [cat, suffixes] of PREGAME_SUFFIX_RULES) {
    for (const s of suffixes) {
      if (bare === s || bare.endsWith(`_${s}`) || name.endsWith(`_${s}`)) return cat;
    }
  }
  return null;
}

const liveMap = buildLiveFeatureMap();

export function computeGroupedFactors(
  baseValue: number,
  shapValues: Record<string, number>,
  modelType: string,
): GroupedFactor[] {
  const totalShap = Object.values(shapValues).reduce((a, b) => a + b, 0);
  const totalLogOdds = baseValue + totalShap;
  const totalProb = sigmoid(totalLogOdds);

  const catShap = new Map<string, number>();

  for (const [feature, shap] of Object.entries(shapValues)) {
    if (EXCLUDED.has(feature)) continue;

    let cat: string | null;
    if (modelType === "pregame") {
      cat = classifyPregameFeature(feature);
    } else {
      cat = liveMap.get(feature) ?? null;
    }

    if (cat) {
      catShap.set(cat, (catShap.get(cat) ?? 0) + shap);
    }
  }

  const groups: GroupedFactor[] = [];
  for (const [category, groupShap] of catShap.entries()) {
    const withoutGroup = totalLogOdds - groupShap;
    const probWithout = sigmoid(withoutGroup);
    const impactPct = Math.round((totalProb - probWithout) * 1000) / 10;
    if (Math.abs(impactPct) >= IMPACT_THRESHOLD) {
      groups.push({ category, impactPct });
    }
  }

  return groups
    .sort((a, b) => Math.abs(b.impactPct) - Math.abs(a.impactPct))
    .slice(0, MAX_GROUPS);
}

export function generateNarrative(
  groups: GroupedFactor[],
  shapValues: Record<string, number>,
): string {
  const pregameShap = shapValues["pregame_blue_win_prob"] ?? 0;
  const displayedTotal = groups.reduce((s, g) => s + Math.abs(g.impactPct), 0);

  if (groups.length === 0 && Math.abs(pregameShap) > 0.1) {
    return "Prediction largely driven by pregame draft and skill analysis.";
  }
  if (groups.length === 0) {
    return "An evenly matched game with no dominant factors.";
  }

  const top = groups[0];
  const direction = top.impactPct > 0 ? "Blue" : "Red";
  const magnitude = Math.abs(top.impactPct);

  let strength = "slight";
  if (magnitude >= NARR.strong_threshold) strength = "strong";
  else if (magnitude >= NARR.moderate_threshold) strength = "moderate";

  let sentence = `${direction} favored by a ${strength} ${top.category.toLowerCase()} edge`;

  if (groups.length > 1 && Math.abs(groups[1].impactPct) >= NARR.second_factor_threshold) {
    const secondDir = groups[1].impactPct > 0 ? "blue" : "red";
    const verb = secondDir === direction.toLowerCase() ? "supported" : "offset";
    sentence += `, ${verb} by ${groups[1].category.toLowerCase()}`;
  }

  if (displayedTotal < Math.abs(pregameShap) * NARR.pregame_dominance_multiplier) {
    sentence += " — largely driven by pregame analysis";
  }

  return sentence + ".";
}

export function buildFactorAnalysis(
  baseValue: number,
  shapValues: Record<string, number>,
  modelType: string,
): FactorAnalysis {
  const groups = computeGroupedFactors(baseValue, shapValues, modelType);
  const narrative = generateNarrative(groups, shapValues);
  return { groups, narrative };
}
