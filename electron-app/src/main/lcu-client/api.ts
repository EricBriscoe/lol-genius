import https from "https";
import type { LCUCredentials, ChampSelectSession, RankedStats } from "./types";
import log from "../log";

const logger = log.scope("lcu-client");

export function createLCUClient(creds: LCUCredentials) {
  const agent = new https.Agent({ rejectUnauthorized: false });
  const auth = Buffer.from(`riot:${creds.password}`).toString("base64");

  function get<T>(path: string): Promise<T | null> {
    return new Promise((resolve) => {
      const req = https.get(
        `https://127.0.0.1:${creds.port}${path}`,
        { agent, timeout: 5000, headers: { Authorization: `Basic ${auth}` } },
        (res) => {
          if (res.statusCode !== 200) {
            res.resume();
            resolve(null);
            return;
          }
          let body = "";
          res.on("data", (chunk: Buffer) => { body += chunk.toString(); });
          res.on("end", () => {
            try { resolve(JSON.parse(body)); }
            catch { resolve(null); }
          });
        },
      );
      req.on("error", (e) => {
        logger.debug("LCU request failed:", path, e.message);
        resolve(null);
      });
      req.on("timeout", () => { req.destroy(); resolve(null); });
    });
  }

  return {
    getGameflowPhase: () => get<string>("/lol-gameflow/v1/gameflow-phase"),
    getChampSelectSession: () => get<ChampSelectSession>("/lol-champ-select/v1/session"),
    getCurrentRankedStats: () => get<RankedStats>("/lol-ranked/v1/current-ranked-stats"),
  };
}

export type LCUClient = ReturnType<typeof createLCUClient>;
