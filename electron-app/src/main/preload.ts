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
  onPlayerIdentity: onChannel("player-identity"),
  onPlayerDataUpdate: onChannel("player-data-update"),
  startPolling: () => ipcRenderer.invoke("start-polling"),
  stopPolling: () => ipcRenderer.invoke("stop-polling"),
  getModelInfo: () => ipcRenderer.invoke("get-model-info"),
  checkForUpdates: () => ipcRenderer.invoke("check-for-updates"),
  setDevMode: (enabled: boolean) => ipcRenderer.invoke("set-dev-mode", enabled),
  getDevMode: () => ipcRenderer.invoke("get-dev-mode"),
  getAppVersion: () => ipcRenderer.invoke("get-app-version"),
  getDdragonVersion: () => ipcRenderer.invoke("get-ddragon-version"),
  forceRestart: () => ipcRenderer.invoke("force-restart"),
  getPlayerIdentity: () => ipcRenderer.invoke("get-player-identity"),
  getMatchHistory: (params: { offset: number; limit: number; championId?: number; queueId?: number }) =>
    ipcRenderer.invoke("get-match-history", params),
  getChampionStats: () => ipcRenderer.invoke("get-champion-stats"),
  getRankedStats: () => ipcRenderer.invoke("get-ranked-stats"),
  refreshPlayerData: () => ipcRenderer.invoke("refresh-player-data"),
});
