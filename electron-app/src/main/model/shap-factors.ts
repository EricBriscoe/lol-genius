import { computeShap } from "../shap/sidecar";
import { getFeatureImportance } from "./inference";

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

  return getFeatureImportance(modelType)
    .slice(0, count)
    .map((f) => ({ feature: f.feature, impact: f.importance }));
}
