import { autoUpdater } from "electron-updater";
import { app, BrowserWindow } from "electron";
import https from "https";
import { createHash } from "crypto";
import { createWriteStream, mkdirSync, existsSync, readFileSync, writeFileSync, unlinkSync, renameSync, rmSync, readdirSync } from "fs";
import { join } from "path";
import log from "./log";
import { safeSend } from "./ipc";
import { getGamePhase } from "./lcu-client/poller";
import { clearTimer } from "./timers";

const logger = log.scope("updater");

const UPDATE_CHECK_INTERVAL = 4 * 60 * 60 * 1000;
const RESTART_POLL_INTERVAL = 30_000;
let updateTimer: ReturnType<typeof setInterval> | null = null;
let restartTimer: ReturnType<typeof setInterval> | null = null;
const modelUpdateInProgress = new Set<string>();

function isUserBusy(): boolean {
  const phase = getGamePhase();
  return phase === "champ_select" || phase === "game_start";
}

function scheduleRestart(win: BrowserWindow): void {
  if (restartTimer) return;

  const tryRestart = () => {
    if (isUserBusy()) {
      logger.info("Deferring auto-restart — user is in game");
      safeSend(win, "app-update-status", { status: "update_ready" });
      return;
    }
    restartTimer = clearTimer(restartTimer);
    logger.info("Auto-restarting to install update");
    safeSend(win, "app-update-status", { status: "restarting" });
    setTimeout(() => {
      if (isUserBusy()) {
        restartTimer = setInterval(tryRestart, RESTART_POLL_INTERVAL);
        return;
      }
      autoUpdater.quitAndInstall(true, true);
    }, 2000);
  };

  tryRestart();
  if (!restartTimer && isUserBusy()) {
    restartTimer = setInterval(tryRestart, RESTART_POLL_INTERVAL);
  }
}

export function setupAppUpdater(win: BrowserWindow): void {
  migrateOldModelLayout();
  cleanStaleStagingDirs();

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on("checking-for-update", () => {
    safeSend(win, "app-update-status", { status: "checking" });
  });

  autoUpdater.on("update-available", () => {
    safeSend(win, "app-update-status", { status: "available" });
  });

  autoUpdater.on("update-not-available", () => {
    safeSend(win, "app-update-status", { status: "not_available" });
  });

  autoUpdater.on("download-progress", (progress) => {
    safeSend(win, "app-update-status", { status: "downloading", percent: Math.round(progress.percent) });
  });

  autoUpdater.on("update-downloaded", () => {
    scheduleRestart(win);
  });

  autoUpdater.on("error", (err) => {
    logger.error("App update error:", err.message);
    safeSend(win, "app-update-status", { status: "error", message: err.message });
  });

  checkForAppUpdates();

  updateTimer = setInterval(() => checkForAppUpdates(), UPDATE_CHECK_INTERVAL);
}

export async function checkForAppUpdates(): Promise<void> {
  try {
    await autoUpdater.checkForUpdatesAndNotify();
  } catch (e) {
    logger.error("Failed to check for app updates:", e);
  }
}

export function forceRestart(): void {
  logger.info("Force restart requested by user");
  autoUpdater.quitAndInstall(true, true);
}

export function stopAppUpdateTimer(): void {
  updateTimer = clearTimer(updateTimer);
  restartTimer = clearTimer(restartTimer);
}

const MODEL_FILES = [
  "model.onnx",
  "model.json",
  "feature_names.json",
  "calibrator.json",
  "feature_importance.json",
];

function modelSubdir(modelType: "live" | "pregame"): string {
  return join("models", modelType);
}

function migrateOldModelLayout(): void {
  const modelsRoot = join(app.getPath("userData"), "models");
  const oldOnnx = join(modelsRoot, "model.onnx");
  if (!existsSync(oldOnnx)) return;

  const liveDir = join(modelsRoot, "live");
  if (existsSync(join(liveDir, "model.onnx"))) return;

  logger.info("Migrating old model layout to models/live/");
  mkdirSync(liveDir, { recursive: true });
  for (const file of [...MODEL_FILES, "checksums.sha256", "version.txt"]) {
    const src = join(modelsRoot, file);
    if (existsSync(src)) {
      renameSync(src, join(liveDir, file));
    }
  }
}

export function getUserModelDir(modelType: "live" | "pregame" = "live"): string {
  return join(app.getPath("userData"), modelSubdir(modelType));
}

export function getModelDir(modelType: "live" | "pregame" = "live"): string {
  const userDir = getUserModelDir(modelType);
  if (existsSync(join(userDir, "model.onnx"))) return userDir;

  const bundled = join(process.resourcesPath ?? app.getAppPath(), modelSubdir(modelType));
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

function cleanStaleStagingDirs(): void {
  const modelsRoot = join(app.getPath("userData"), "models");
  if (!existsSync(modelsRoot)) return;
  try {
    for (const entry of readdirSync(modelsRoot)) {
      if (entry.startsWith(".staging-")) {
        const stagingPath = join(modelsRoot, entry);
        logger.info("Cleaning stale staging dir:", stagingPath);
        rmSync(stagingPath, { recursive: true, force: true });
      }
    }
  } catch (e) {
    logger.warn("Failed to clean staging dirs:", e);
  }
}

export async function checkForModelUpdate(modelType: "live" | "pregame" = "live"): Promise<boolean> {
  if (modelUpdateInProgress.has(modelType)) {
    logger.info(`${modelType} model update already in progress, skipping`);
    return false;
  }

  modelUpdateInProgress.add(modelType);
  try {
    return await doCheckForModelUpdate(modelType);
  } finally {
    modelUpdateInProgress.delete(modelType);
  }
}

async function doCheckForModelUpdate(modelType: "live" | "pregame"): Promise<boolean> {
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
          if (res.statusCode === 403) {
            logger.warn(`GitHub API rate limited for ${modelType} model check:`, body.slice(0, 200));
            resolve(false);
            return;
          }
          if (res.statusCode !== 200) {
            logger.warn(`GitHub API returned ${res.statusCode} for ${modelType} model check:`, body.slice(0, 200));
            resolve(false);
            return;
          }
          const releases = JSON.parse(body);
          if (!Array.isArray(releases)) {
            logger.warn(`Unexpected GitHub API response for ${modelType}:`, body.slice(0, 200));
            resolve(false);
            return;
          }
          const modelRelease = releases.find(
            (r: { tag_name: string }) =>
              r.tag_name.startsWith("model-v") && r.tag_name.includes(tagPattern),
          );
          if (!modelRelease) { resolve(false); return; }

          const currentVersion = getModelVersion(modelType);
          if (currentVersion === modelRelease.tag_name) { resolve(false); return; }

          const stagingDir = join(app.getPath("userData"), "models", `.staging-${modelType}`);
          rmSync(stagingDir, { recursive: true, force: true });
          mkdirSync(stagingDir, { recursive: true });

          const assets = modelRelease.assets as { name: string; browser_download_url: string }[];
          logger.debug(`Found ${modelType} model release:`, modelRelease.tag_name, "assets:", assets.length);
          const checksumAsset = assets.find((a) => a.name === "checksums.sha256");

          const modelDownloads = MODEL_FILES.flatMap((file) => {
            const asset = assets.find((a) => a.name === file);
            if (!asset) return [];
            logger.debug("Downloading:", file);
            return [downloadFile(asset.browser_download_url, join(stagingDir, file))];
          });

          const downloaded = modelDownloads.length;
          if (checksumAsset) {
            modelDownloads.push(downloadFile(checksumAsset.browser_download_url, join(stagingDir, "checksums.sha256")));
          }
          try {
            await Promise.all(modelDownloads);
          } catch (e) {
            logger.error(`Download failed for ${modelType} model, cleaning up staging:`, e);
            rmSync(stagingDir, { recursive: true, force: true });
            resolve(false);
            return;
          }

          if (downloaded > 0) {
            if (checksumAsset && !verifyChecksums(stagingDir)) {
              logger.error("Checksum verification failed, removing staged files");
              rmSync(stagingDir, { recursive: true, force: true });
              resolve(false);
              return;
            }

            const outDir = getUserModelDir(modelType);
            mkdirSync(outDir, { recursive: true });
            for (const file of [...MODEL_FILES, "checksums.sha256"]) {
              const src = join(stagingDir, file);
              if (existsSync(src)) {
                renameSync(src, join(outDir, file));
              }
            }
            writeFileSync(join(outDir, "version.txt"), modelRelease.tag_name);
            rmSync(stagingDir, { recursive: true, force: true });
            resolve(true);
          } else {
            rmSync(stagingDir, { recursive: true, force: true });
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
      logger.error(`Checksum file references missing file: ${filename}`);
      return false;
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

function silentUnlink(path: string): void {
  try { unlinkSync(path); } catch {}
}

function downloadFile(url: string, dest: string, maxRedirects = 5): Promise<void> {
  return new Promise((resolve, reject) => {
    if (maxRedirects <= 0) {
      reject(new Error(`Too many redirects for ${url}`));
      return;
    }

    const tmpDest = dest + ".tmp";
    const req = https.get(url, { headers: { "User-Agent": "lol-genius-electron" }, timeout: 30_000 }, (res) => {
      if (res.statusCode === 301 || res.statusCode === 302 || res.statusCode === 307 || res.statusCode === 308) {
        res.resume();
        downloadFile(res.headers.location!, dest, maxRedirects - 1).then(resolve, reject);
        return;
      }
      if (!res.statusCode || res.statusCode < 200 || res.statusCode >= 300) {
        res.resume();
        reject(new Error(`Download failed: HTTP ${res.statusCode} for ${url}`));
        return;
      }
      const file = createWriteStream(tmpDest);
      res.on("error", (e) => {
        file.destroy();
        silentUnlink(tmpDest);
        reject(e);
      });
      res.pipe(file);
      file.on("finish", () => {
        file.close();
        try {
          renameSync(tmpDest, dest);
          resolve();
        } catch (e) {
          reject(e);
        }
      });
      file.on("error", (e) => {
        silentUnlink(tmpDest);
        reject(e);
      });
    });
    req.on("error", (e) => {
      silentUnlink(tmpDest);
      reject(e);
    });
    req.on("timeout", () => {
      req.destroy();
      silentUnlink(tmpDest);
      reject(new Error(`Download timed out: ${url}`));
    });
  });
}
