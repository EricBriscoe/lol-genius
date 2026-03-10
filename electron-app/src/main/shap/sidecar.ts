import { execFile } from "child_process";
import { existsSync } from "fs";
import { join } from "path";
import { app } from "electron";
import log from "../log";

const logger = log.scope("shap");

export interface ShapResult {
  baseValue: number;
  shapValues: Record<string, number>;
}

let sidecarPath: string | null = null;

function findSidecar(): string | null {
  if (sidecarPath !== null) return sidecarPath;

  const candidates = [
    join(process.resourcesPath ?? "", "sidecar", "shap_predict.exe"),
    join(process.resourcesPath ?? "", "sidecar", "shap_predict"),
    join(app.getAppPath(), "sidecar", "dist", "shap_predict.exe"),
    join(app.getAppPath(), "sidecar", "dist", "shap_predict"),
  ];

  for (const p of candidates) {
    if (existsSync(p)) {
      sidecarPath = p;
      return p;
    }
  }
  return null;
}

export async function computeShap(
  modelDir: string,
  features: Record<string, number>,
): Promise<ShapResult | null> {
  const binary = findSidecar();
  if (!binary) return null;
  logger.debug("Sidecar binary:", binary);

  const modelPath = join(modelDir, "model.json");
  if (!existsSync(modelPath)) return null;
  logger.debug("SHAP input:", Object.keys(features).length, "features");

  return new Promise((resolve) => {
    const child = execFile(
      binary,
      [modelPath],
      { timeout: 30_000, maxBuffer: 1024 * 1024 },
      (error, stdout) => {
        if (error) {
          logger.warn("SHAP sidecar error:", error.message);
          resolve(null);
          return;
        }
        try {
          const parsed = JSON.parse(stdout);
          if ("base_value" in parsed) {
            resolve({ baseValue: parsed.base_value, shapValues: parsed.shap_values });
          } else {
            resolve({ baseValue: 0, shapValues: parsed });
          }
        } catch (e) {
          logger.warn("SHAP invalid JSON:", e);
          resolve(null);
        }
      },
    );
    child.stdin?.write(JSON.stringify(features));
    child.stdin?.end();
  });
}
