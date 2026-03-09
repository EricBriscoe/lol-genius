import { computeShap } from "../shap/sidecar";
import { getFeatureImportance, predict } from "./inference";

export async function computeTopFactors(
  modelDir: string | null,
  features: Record<string, number>,
  modelType = "live",
  count = 8,
): Promise<{ feature: string; impact: number }[]> {
  if (modelDir) {
    const shapValues = await computeShap(modelDir, features);
    if (shapValues) {
      return Object.entries(shapValues)
        .map(([feature, impact]) => ({ feature, impact }))
        .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
        .slice(0, count);
    }
  }

  const staticImportance = getFeatureImportance(modelType);
  const topFeatures = staticImportance.slice(0, count);
  if (topFeatures.length === 0) return [];

  const baseProb = await predict(features, modelType);
  const results: { feature: string; impact: number }[] = [];

  for (const { feature } of topFeatures) {
    const modified = { ...features, [feature]: 0 };
    const modifiedProb = await predict(modified, modelType);
    results.push({ feature, impact: baseProb - modifiedProb });
  }

  return results
    .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
    .slice(0, count);
}
