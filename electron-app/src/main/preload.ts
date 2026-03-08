import { contextBridge, ipcRenderer } from "electron";

function onChannel(channel: string) {
  return (cb: (data: never) => void) => {
    const listener = (_: unknown, d: never) => cb(d);
    ipcRenderer.on(channel, listener);
    return () => ipcRenderer.removeListener(channel, listener);
  };
}

contextBridge.exposeInMainWorld("lolGenius", {
  onPredictionUpdate: onChannel("prediction-update"),
  onConnectionStatus: onChannel("connection-status"),
  onAppUpdateStatus: onChannel("app-update-status"),
  onChampSelectUpdate: onChannel("champ-select-update"),
  onGamePhaseChange: onChannel("game-phase-change"),
  onDevLog: onChannel("dev-log"),
  startPolling: () => ipcRenderer.invoke("start-polling"),
  stopPolling: () => ipcRenderer.invoke("stop-polling"),
  getModelInfo: () => ipcRenderer.invoke("get-model-info"),
  checkForUpdates: () => ipcRenderer.invoke("check-for-updates"),
  checkAppUpdates: () => ipcRenderer.invoke("check-app-updates"),
  installAppUpdate: () => ipcRenderer.invoke("install-app-update"),
  setDevMode: (enabled: boolean) => ipcRenderer.invoke("set-dev-mode", enabled),
  getDevMode: () => ipcRenderer.invoke("get-dev-mode"),
  getAppVersion: () => ipcRenderer.invoke("get-app-version"),
  setAlwaysOnTop: (enabled: boolean) => ipcRenderer.invoke("set-always-on-top", enabled),
  getAlwaysOnTop: () => ipcRenderer.invoke("get-always-on-top"),
});
