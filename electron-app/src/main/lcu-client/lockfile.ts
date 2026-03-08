import { existsSync, readFileSync, watch, type FSWatcher } from "fs";
import { dirname } from "path";
import type { LCUCredentials } from "./types";

const LOCKFILE_PATHS =
  process.platform === "darwin"
    ? ["/Applications/League of Legends.app/Contents/LoL/lockfile"]
    : [
        "C:\\Riot Games\\League of Legends\\lockfile",
        "D:\\Riot Games\\League of Legends\\lockfile",
        "C:\\Program Files\\Riot Games\\League of Legends\\lockfile",
        "C:\\Program Files (x86)\\Riot Games\\League of Legends\\lockfile",
      ];

export function findLockfile(): string | null {
  for (const p of LOCKFILE_PATHS) {
    if (existsSync(p)) return p;
  }
  return null;
}

export function parseLockfile(content: string): LCUCredentials | null {
  const parts = content.trim().split(":");
  if (parts.length < 5) return null;
  const pid = parseInt(parts[1], 10);
  const port = parseInt(parts[2], 10);
  const password = parts[3];
  if (isNaN(pid) || isNaN(port) || !password) return null;
  return { port, password, pid };
}

export function readLockfile(path: string): LCUCredentials | null {
  try {
    const content = readFileSync(path, "utf-8");
    return parseLockfile(content);
  } catch {
    return null;
  }
}

export function watchLockfile(
  cb: (exists: boolean, creds: LCUCredentials | null) => void,
): () => void {
  const watchers: FSWatcher[] = [];

  for (const p of LOCKFILE_PATHS) {
    const dir = dirname(p);
    if (!existsSync(dir)) continue;

    try {
      const watcher = watch(dir, (_, filename) => {
        if (filename === "lockfile") {
          if (existsSync(p)) {
            cb(true, readLockfile(p));
          } else {
            cb(false, null);
          }
        }
      });
      watchers.push(watcher);
    } catch {
      // dir may not be watchable
    }
  }

  return () => watchers.forEach((w) => w.close());
}
