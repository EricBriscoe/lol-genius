import { computeShap } from "../shap/sidecar";
import { buildFactorAnalysis } from "./shap-categories";
import type { FactorAnalysis } from "../../renderer/types";

export async function computeTopFactors(
  modelDir: string | null,
  features: Record<string, number>,
  modelType = "live",
): Promise<FactorAnalysis> {
  if (modelDir) {
    const result = await computeShap(modelDir, features, modelType);
    if (result) {
      if (result.factorAnalysis) {
        return result.factorAnalysis;
      }
      return buildFactorAnalysis(result.baseValue, result.shapValues, modelType);
    }
  }
  return { groups: [], narrative: "" };
}
