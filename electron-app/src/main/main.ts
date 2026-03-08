import { app, BrowserWindow, ipcMain } from "electron";
import { join } from "path";
import { loadModel, getFeatureNames } from "./model/inference";
import { startPolling, stopPolling, isPolling, setPregameData } from "./live-client/poller";
import { startLCUPolling, stopLCUPolling } from "./lcu-client/poller";
import { setupAppUpdater, getModelDir, getModelVersion, checkForModelUpdate } from "./updater";
import { loadChampionData } from "./model/ddragon";
import log, { setDevMode, isDevMode, loadDevModePreference, setLogWindow } from "./log";

const logger = log.scope("main");

let mainWindow: BrowserWindow | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 720,
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

  const resourcesPath = process.resourcesPath ?? app.getAppPath();
  loadChampionData(resourcesPath);

  const liveModelDir = getModelDir("live");
  try {
    await loadModel(liveModelDir, "live");
  } catch (e) {
    logger.warn("Live model not loaded:", e);
  }

  const pregameModelDir = getModelDir("pregame");
  try {
    await loadModel(pregameModelDir, "pregame");
  } catch (e) {
    logger.warn("Pregame model not loaded:", e);
  }

  const liveUpdated = await checkForModelUpdate("live");
  if (liveUpdated) {
    try { await loadModel(getModelDir("live"), "live"); }
    catch (e) { logger.error("Live model reload failed:", e); }
  }

  const pregameUpdated = await checkForModelUpdate("pregame");
  if (pregameUpdated) {
    try { await loadModel(getModelDir("pregame"), "pregame"); }
    catch (e) { logger.error("Pregame model reload failed:", e); }
  }

  if (mainWindow) {
    if (!isPolling()) {
      startPolling(mainWindow, getModelDir("live"));
    }

    startLCUPolling(mainWindow, getModelDir("live"));

    ipcMain.on("game-phase-change", (_, data: { phase: string; pregameProb?: number; pregameSummary?: Record<string, number> }) => {
      if (data.phase === "in_game" && data.pregameProb != null) {
        setPregameData(data.pregameProb, data.pregameSummary ?? null);
      }
    });
  }
});

app.on("window-all-closed", () => {
  stopPolling();
  stopLCUPolling();
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
  const liveUpdated = await checkForModelUpdate("live");
  if (liveUpdated) {
    await loadModel(getModelDir("live"), "live");
  }
  const pregameUpdated = await checkForModelUpdate("pregame");
  if (pregameUpdated) {
    await loadModel(getModelDir("pregame"), "pregame");
  }
  return liveUpdated || pregameUpdated;
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
