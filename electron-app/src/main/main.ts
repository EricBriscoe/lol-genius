import { app, BrowserWindow, ipcMain } from "electron";
import { join } from "path";
import { loadModel, getFeatureNames } from "./model/inference";
import { startPolling, stopPolling, isPolling } from "./live-client/poller";
import { setupAppUpdater, getModelDir, getModelVersion, checkForModelUpdate } from "./updater";

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
  });
}

app.whenReady().then(async () => {
  createWindow();

  if (mainWindow) {
    setupAppUpdater(mainWindow);
  }

  const modelDir = getModelDir();
  try {
    await loadModel(modelDir);
  } catch {
    // Model may not be bundled yet
  }

  const updated = await checkForModelUpdate();
  if (updated) {
    try {
      await loadModel(getModelDir());
    } catch {
      // ignore
    }
  }

  if (mainWindow && !isPolling()) {
    startPolling(mainWindow, getModelDir());
  }
});

app.on("window-all-closed", () => {
  stopPolling();
  app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

ipcMain.handle("start-polling", () => {
  if (mainWindow) {
    const modelDir = getModelDir();
    loadModel(modelDir).then(() => {
      startPolling(mainWindow!, modelDir);
    });
  }
});

ipcMain.handle("stop-polling", () => {
  stopPolling();
});

ipcMain.handle("get-model-info", () => ({
  version: getModelVersion(),
  featureCount: getFeatureNames().length,
  modelDir: getModelDir(),
  polling: isPolling(),
}));

ipcMain.handle("check-for-updates", async () => {
  const updated = await checkForModelUpdate();
  if (updated) {
    await loadModel(getModelDir());
  }
  return updated;
});
