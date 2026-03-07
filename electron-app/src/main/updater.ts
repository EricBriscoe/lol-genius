import { autoUpdater } from "electron-updater";
import { app, BrowserWindow } from "electron";
import https from "https";
import { createWriteStream, mkdirSync, existsSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";

export function setupAppUpdater(win: BrowserWindow): void {
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on("update-available", () => {
    win.webContents.send("app-update-status", { status: "available" });
  });

  autoUpdater.on("update-downloaded", () => {
    win.webContents.send("app-update-status", { status: "downloaded" });
  });

  autoUpdater.checkForUpdatesAndNotify();
}

const MODEL_FILES = [
  "model.onnx",
  "model.json",
  "feature_names.json",
  "calibrator.json",
  "feature_importance.json",
];

export function getModelDir(): string {
  const userDir = join(app.getPath("userData"), "models");
  if (existsSync(join(userDir, "model.onnx"))) return userDir;

  const bundled = join(process.resourcesPath ?? app.getAppPath(), "models");
  if (existsSync(join(bundled, "model.onnx"))) return bundled;

  return userDir;
}

export function getModelVersion(): string | null {
  const dir = getModelDir();
  const versionFile = join(dir, "version.txt");
  if (existsSync(versionFile)) {
    return readFileSync(versionFile, "utf-8").trim();
  }
  return null;
}

export async function checkForModelUpdate(): Promise<boolean> {
  return new Promise((resolve) => {
    const options = {
      hostname: "api.github.com",
      path: "/repos/EricBriscoe/lol-genius/releases?per_page=10",
      headers: { "User-Agent": "lol-genius-electron" },
    };

    https.get(options, (res) => {
      let body = "";
      res.on("data", (chunk: Buffer) => { body += chunk.toString(); });
      res.on("end", async () => {
        try {
          const releases = JSON.parse(body);
          const modelRelease = releases.find(
            (r: { tag_name: string }) => r.tag_name.startsWith("model-v"),
          );
          if (!modelRelease) { resolve(false); return; }

          const currentVersion = getModelVersion();
          if (currentVersion === modelRelease.tag_name) { resolve(false); return; }

          const outDir = join(app.getPath("userData"), "models");
          mkdirSync(outDir, { recursive: true });

          const assets = modelRelease.assets as { name: string; browser_download_url: string }[];
          let downloaded = 0;
          for (const file of MODEL_FILES) {
            const asset = assets.find((a) => a.name === file);
            if (!asset) continue;

            await downloadFile(asset.browser_download_url, join(outDir, file));
            downloaded++;
          }

          if (downloaded > 0) {
            writeFileSync(join(outDir, "version.txt"), modelRelease.tag_name);
            resolve(true);
          } else {
            resolve(false);
          }
        } catch {
          resolve(false);
        }
      });
    }).on("error", () => resolve(false));
  });
}

function downloadFile(url: string, dest: string): Promise<void> {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { "User-Agent": "lol-genius-electron" } }, (res) => {
      if (res.statusCode === 302 || res.statusCode === 301) {
        downloadFile(res.headers.location!, dest).then(resolve, reject);
        return;
      }
      const file = createWriteStream(dest);
      res.pipe(file);
      file.on("finish", () => { file.close(); resolve(); });
      file.on("error", reject);
    }).on("error", reject);
  });
}
