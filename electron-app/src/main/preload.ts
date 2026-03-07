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
  startPolling: () => ipcRenderer.invoke("start-polling"),
  stopPolling: () => ipcRenderer.invoke("stop-polling"),
  getModelInfo: () => ipcRenderer.invoke("get-model-info"),
  checkForUpdates: () => ipcRenderer.invoke("check-for-updates"),
});
