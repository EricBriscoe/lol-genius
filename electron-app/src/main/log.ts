import log from "electron-log/main";
import { app } from "electron";
import { readFileSync, writeFileSync, existsSync } from "fs";
import { join } from "path";
import type { BrowserWindow } from "electron";

log.transports.file.level = "info";
log.transports.console.level = "debug";
log.transports.file.format = "{y}-{m}-{d} {h}:{i}:{s} [{level}] {scope}: {text}";

let devMode = false;
let logWindow: BrowserWindow | null = null;

function getPrefsPath(): string {
  return join(app.getPath("userData"), "dev-mode.json");
}

export function loadDevModePreference(): boolean {
  try {
    const p = getPrefsPath();
    if (existsSync(p)) {
      return JSON.parse(readFileSync(p, "utf-8")).enabled === true;
    }
  } catch (e) {
    log.warn("Failed to read dev-mode preference:", e);
  }
  return false;
}

export function setDevMode(enabled: boolean): void {
  devMode = enabled;
  log.transports.file.level = enabled ? "debug" : "info";
  log.transports.console.level = "debug";

  try {
    writeFileSync(getPrefsPath(), JSON.stringify({ enabled }));
  } catch (e) {
    log.warn("Failed to write dev-mode preference:", e);
  }
}

export function isDevMode(): boolean {
  return devMode;
}

export function setLogWindow(win: BrowserWindow | null): void {
  logWindow = win;
}

log.hooks.push((message) => {
  if (devMode && logWindow && !logWindow.isDestroyed()) {
    logWindow.webContents.send("dev-log", {
      timestamp: new Date().toISOString(),
      scope: (message.scope as string) ?? "",
      level: message.level ?? "info",
      message: message.data?.map((d: unknown) =>
        typeof d === "string" ? d : JSON.stringify(d),
      ).join(" ") ?? "",
    });
  }
  return message;
});

export default log;
