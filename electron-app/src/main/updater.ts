import { autoUpdater } from "electron-updater";
import { app, BrowserWindow } from "electron";
import https from "https";
import { createHash } from "crypto";
import { createWriteStream, mkdirSync, existsSync, readFileSync, writeFileSync, unlinkSync } from "fs";
import { join } from "path";
import log from "./log";

const logger = log.scope("updater");

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

export function getModelDir(modelType: "live" | "pregame" = "live"): string {
  const subdir = modelType === "pregame" ? join("models", "pregame") : "models";

  const userDir = join(app.getPath("userData"), subdir);
  if (existsSync(join(userDir, "model.onnx"))) return userDir;

  const bundled = join(process.resourcesPath ?? app.getAppPath(), subdir);
  if (existsSync(join(bundled, "model.onnx"))) return bundled;

  return userDir;
}

export function getModelVersion(modelType: "live" | "pregame" = "live"): string | null {
  const dir = getModelDir(modelType);
  const versionFile = join(dir, "version.txt");
  if (existsSync(versionFile)) {
    return readFileSync(versionFile, "utf-8").trim();
  }
  return null;
}

export async function checkForModelUpdate(modelType: "live" | "pregame" = "live"): Promise<boolean> {
  const tagPattern = modelType === "pregame" ? "pregame" : "live";

  return new Promise((resolve) => {
    const options = {
      hostname: "api.github.com",
      path: "/repos/EricBriscoe/lol-genius/releases?per_page=20",
      headers: { "User-Agent": "lol-genius-electron" },
    };

    https.get(options, (res) => {
      let body = "";
      res.on("data", (chunk: Buffer) => { body += chunk.toString(); });
      res.on("end", async () => {
        try {
          const releases = JSON.parse(body);
          const modelRelease = releases.find(
            (r: { tag_name: string }) =>
              r.tag_name.startsWith("model-v") && r.tag_name.includes(tagPattern),
          );
          if (!modelRelease) { resolve(false); return; }

          const currentVersion = getModelVersion(modelType);
          if (currentVersion === modelRelease.tag_name) { resolve(false); return; }

          const outDir = modelType === "pregame"
            ? join(app.getPath("userData"), "models", "pregame")
            : join(app.getPath("userData"), "models");
          mkdirSync(outDir, { recursive: true });

          const assets = modelRelease.assets as { name: string; browser_download_url: string }[];
          logger.debug(`Found ${modelType} model release:`, modelRelease.tag_name, "assets:", assets.length);
          const checksumAsset = assets.find((a) => a.name === "checksums.sha256");

          let downloaded = 0;
          for (const file of MODEL_FILES) {
            const asset = assets.find((a) => a.name === file);
            if (!asset) continue;
            logger.debug("Downloading:", file);

            await downloadFile(asset.browser_download_url, join(outDir, file));
            downloaded++;
          }

          if (checksumAsset) {
            await downloadFile(checksumAsset.browser_download_url, join(outDir, "checksums.sha256"));
          }

          if (downloaded > 0) {
            if (checksumAsset && !verifyChecksums(outDir)) {
              logger.error("Checksum verification failed, removing downloaded model files");
              for (const file of MODEL_FILES) {
                const path = join(outDir, file);
                if (existsSync(path)) unlinkSync(path);
              }
              resolve(false);
              return;
            }
            writeFileSync(join(outDir, "version.txt"), modelRelease.tag_name);
            resolve(true);
          } else {
            resolve(false);
          }
        } catch (e) {
          logger.error(`${modelType} model update check failed:`, e);
          resolve(false);
        }
      });
    }).on("error", (e) => {
      logger.error(`${modelType} model update request failed:`, e.message);
      resolve(false);
    });
  });
}

function verifyChecksums(dir: string): boolean {
  const checksumFile = join(dir, "checksums.sha256");
  if (!existsSync(checksumFile)) return true;

  const lines = readFileSync(checksumFile, "utf-8").trim().split("\n");
  for (const line of lines) {
    const [expectedHash, filename] = line.trim().split(/\s+/);
    if (!expectedHash || !filename) continue;

    const filePath = join(dir, filename);
    if (!existsSync(filePath)) {
      logger.warn(`Checksum file references missing file: ${filename}`);
      continue;
    }

    const hash = createHash("sha256");
    hash.update(readFileSync(filePath));
    const actual = hash.digest("hex");

    if (actual !== expectedHash) {
      logger.error(`Checksum mismatch for ${filename}: expected ${expectedHash}, got ${actual}`);
      return false;
    }
  }

  logger.info("All checksums verified");
  return true;
}

function downloadFile(url: string, dest: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { "User-Agent": "lol-genius-electron" }, timeout: 30_000 }, (res) => {
      if (res.statusCode === 302 || res.statusCode === 301) {
        downloadFile(res.headers.location!, dest).then(resolve, reject);
        return;
      }
      if (!res.statusCode || res.statusCode < 200 || res.statusCode >= 400) {
        res.resume();
        reject(new Error(`Download failed: HTTP ${res.statusCode} for ${url}`));
        return;
      }
      const file = createWriteStream(dest);
      res.pipe(file);
      file.on("finish", () => { file.close(); resolve(); });
      file.on("error", reject);
    });
    req.on("error", reject);
    req.on("timeout", () => { req.destroy(); reject(new Error(`Download timed out: ${url}`)); });
  });
}
