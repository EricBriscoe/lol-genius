import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("lolGenius", {
  onPredictionUpdate: (cb: (data: unknown) => void) => {
    const listener = (_: unknown, d: unknown) => cb(d);
    ipcRenderer.on("prediction-update", listener);
    return () => ipcRenderer.removeListener("prediction-update", listener);
  },
  onConnectionStatus: (cb: (status: string) => void) => {
    const listener = (_: unknown, s: string) => cb(s);
    ipcRenderer.on("connection-status", listener);
    return () => ipcRenderer.removeListener("connection-status", listener);
  },
  onAppUpdateStatus: (cb: (data: unknown) => void) => {
    const listener = (_: unknown, d: unknown) => cb(d);
    ipcRenderer.on("app-update-status", listener);
    return () => ipcRenderer.removeListener("app-update-status", listener);
  },
  onChampSelectUpdate: (cb: (data: unknown) => void) => {
    const listener = (_: unknown, d: unknown) => cb(d);
    ipcRenderer.on("champ-select-update", listener);
    return () => ipcRenderer.removeListener("champ-select-update", listener);
  },
  onGamePhaseChange: (cb: (data: unknown) => void) => {
    const listener = (_: unknown, d: unknown) => cb(d);
    ipcRenderer.on("game-phase-change", listener);
    return () => ipcRenderer.removeListener("game-phase-change", listener);
  },
  startPolling: () => ipcRenderer.invoke("start-polling"),
  stopPolling: () => ipcRenderer.invoke("stop-polling"),
  getModelInfo: () => ipcRenderer.invoke("get-model-info"),
  checkForUpdates: () => ipcRenderer.invoke("check-for-updates"),
  setDevMode: (enabled: boolean) => ipcRenderer.invoke("set-dev-mode", enabled),
  getDevMode: () => ipcRenderer.invoke("get-dev-mode"),
  onDevLog: (cb: (entry: unknown) => void) => {
    const listener = (_: unknown, d: unknown) => cb(d);
    ipcRenderer.on("dev-log", listener);
    return () => ipcRenderer.removeListener("dev-log", listener);
  },
});
