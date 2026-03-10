import { app, BrowserWindow, ipcMain, screen } from "electron";
import { join } from "path";
import { readFileSync, writeFileSync, existsSync } from "fs";
import { loadModel, getFeatureNames } from "./model/inference";
import { startPolling, stopPolling, isPolling } from "./live-client/poller";
import { startLCUPolling, stopLCUPolling } from "./lcu-client/poller";
import { initPlayerData, shutdownPlayerData } from "./player-data/index";
import { setupAppUpdater, getModelDir, getModelVersion, checkForModelUpdate, checkForAppUpdates, stopAppUpdateTimer, forceRestart } from "./updater";
import { safeSend } from "./ipc";
import { loadChampionData, getChampionVersion } from "./model/ddragon";
import log, { setDevMode, isDevMode, loadDevModePreference, setLogWindow } from "./log";
import { clearTimer } from "./timers";

const logger = log.scope("main");

let mainWindow: BrowserWindow | null = null;
let modelUpdateTimer: ReturnType<typeof setInterval> | null = null;

const MODEL_UPDATE_INTERVAL = 30 * 60 * 1000;

function stopModelUpdateTimer(): void {
  modelUpdateTimer = clearTimer(modelUpdateTimer);
}

process.on("uncaughtException", (error) => {
  logger.error("Uncaught exception:", error);
});

process.on("unhandledRejection", (reason) => {
  logger.error("Unhandled rejection:", reason);
});

interface WindowState { x: number; y: number; width: number; height: number }

function getWindowStatePath(): string {
  return join(app.getPath("userData"), "window-state.json");
}

function loadWindowState(): WindowState | null {
  try {
    const p = getWindowStatePath();
    if (!existsSync(p)) return null;
    const state: WindowState = JSON.parse(readFileSync(p, "utf-8"));
    const display = screen.getDisplayMatching({
      x: state.x, y: state.y, width: state.width, height: state.height,
    });
    if (!display) return null;
    const { x, y, width, height } = display.workArea;
    if (state.x + state.width < x + 50 || state.x > x + width - 50 ||
        state.y + state.height < y + 50 || state.y > y + height - 50) {
      return null;
    }
    return state;
  } catch {
    return null;
  }
}

function saveWindowState(win: BrowserWindow): void {
  if (win.isMinimized() || win.isMaximized()) return;
  const bounds = win.getBounds();
  try {
    writeFileSync(getWindowStatePath(), JSON.stringify(bounds));
  } catch (e) {
    logger.warn("Failed to save window state:", e);
  }
}

async function updateAllModels(): Promise<boolean> {
  const [live, pregame] = await Promise.all([
    loadAndUpdateModel("live"),
    loadAndUpdateModel("pregame"),
  ]);
  return live || pregame;
}

async function loadAndUpdateModel(modelType: "live" | "pregame"): Promise<boolean> {
  try {
    await loadModel(getModelDir(modelType), modelType);
  } catch (e) {
    logger.warn(`${modelType} model not loaded:`, e);
  }

  const updated = await checkForModelUpdate(modelType);
  if (updated) {
    try { await loadModel(getModelDir(modelType), modelType, true); }
    catch (e) { logger.error(`${modelType} model reload failed:`, e); }
  }
  return updated;
}

function createWindow(): void {
  const saved = loadWindowState();
  mainWindow = new BrowserWindow({
    width: saved?.width ?? 900,
    height: saved?.height ?? 720,
    x: saved?.x,
    y: saved?.y,
    minWidth: 600,
    minHeight: 500,
    title: "lol-genius",
    backgroundColor: "#0f1117",
    webPreferences: {
      preload: join(__dirname, "../preload/preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  let saveTimeout: ReturnType<typeof setTimeout> | null = null;
  const debouncedSave = () => {
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => { if (mainWindow) saveWindowState(mainWindow); }, 500);
  };
  mainWindow.on("resize", debouncedSave);
  mainWindow.on("move", debouncedSave);

  if (process.env.ELECTRON_RENDERER_URL) {
    mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
    stopPolling();
    stopLCUPolling();
  });
}

app.whenReady().then(async () => {
  createWindow();

  if (mainWindow) {
    setLogWindow(mainWindow);
    setupAppUpdater(mainWindow);

    if (loadDevModePreference()) {
      setDevMode(true);
      mainWindow.webContents.openDevTools();
    }
  }

  const resourcesPath = app.isPackaged
    ? process.resourcesPath
    : join(app.getAppPath(), "..", "data");
  try {
    loadChampionData(resourcesPath);
  } catch (e) {
    logger.error("Failed to load champion data:", e);
    safeSend(mainWindow, "connection-status", "ddragon_error");
  }

  await updateAllModels();

  modelUpdateTimer = setInterval(async () => {
    if (await updateAllModels()) {
      safeSend(mainWindow, "app-update-status", { status: "model_updated" });
    }
  }, MODEL_UPDATE_INTERVAL);

  if (mainWindow) {
    initPlayerData(mainWindow);

    if (!isPolling()) {
      startPolling(mainWindow, getModelDir("live"));
    }

    startLCUPolling(mainWindow);
  }
});

app.on("window-all-closed", () => {
  stopModelUpdateTimer();
  stopAppUpdateTimer();
  stopPolling();
  stopLCUPolling();
  shutdownPlayerData();
  app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

ipcMain.handle("start-polling", () => {
  if (mainWindow) {
    const win = mainWindow;
    const modelDir = getModelDir("live");
    loadModel(modelDir, "live").then(() => {
      startPolling(win, modelDir);
    }).catch((e) => {
      logger.error("Model load failed for polling:", e);
    });
  }
});

ipcMain.handle("stop-polling", () => {
  stopPolling();
});

ipcMain.handle("get-model-info", () => ({
  version: getModelVersion("live"),
  featureCount: getFeatureNames("live").length,
  modelDir: getModelDir("live"),
  polling: isPolling(),
  pregameVersion: getModelVersion("pregame"),
  pregameFeatureCount: getFeatureNames("pregame").length,
}));

ipcMain.handle("check-for-updates", async () => {
  checkForAppUpdates();
  return updateAllModels();
});

ipcMain.handle("set-dev-mode", (_, enabled: boolean) => {
  setDevMode(enabled);
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (enabled) {
      mainWindow.webContents.openDevTools();
    } else {
      mainWindow.webContents.closeDevTools();
    }
  }
});

ipcMain.handle("get-dev-mode", () => isDevMode());
ipcMain.handle("get-app-version", () => app.getVersion());
ipcMain.handle("get-ddragon-version", () => getChampionVersion());
ipcMain.handle("force-restart", () => forceRestart());
ipcMain.handle("set-always-on-top", (_, enabled: boolean) => mainWindow?.setAlwaysOnTop(enabled));
ipcMain.handle("get-always-on-top", () => mainWindow?.isAlwaysOnTop() ?? false);
