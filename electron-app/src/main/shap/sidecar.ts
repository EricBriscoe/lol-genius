import { execFile } from "child_process";
import { existsSync } from "fs";
import { join } from "path";
import { app } from "electron";

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
): Promise<Record<string, number> | null> {
  const binary = findSidecar();
  if (!binary) return null;

  const modelPath = join(modelDir, "model.json");
  if (!existsSync(modelPath)) return null;

  return new Promise((resolve) => {
    const child = execFile(
      binary,
      [modelPath],
      { timeout: 30_000, maxBuffer: 1024 * 1024 },
      (error, stdout) => {
        if (error) {
          resolve(null);
          return;
        }
        try {
          resolve(JSON.parse(stdout));
        } catch {
          resolve(null);
        }
      },
    );
    child.stdin?.write(JSON.stringify(features));
    child.stdin?.end();
  });
}
