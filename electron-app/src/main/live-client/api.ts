import https from "https";
import log from "../log";

const logger = log.scope("live-client");
const agent = new https.Agent({ rejectUnauthorized: false });

export async function fetchLiveGameData(): Promise<Record<string, unknown> | null> {
  return new Promise((resolve) => {
    const req = https.get(
      "https://127.0.0.1:2999/liveclientdata/allgamedata",
      { agent, timeout: 5000 },
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
          catch (e) { logger.debug("JSON parse failed:", e); resolve(null); }
        });
      },
    );
    req.on("error", (e) => {
      logger.debug("Live client unreachable:", e.message);
      resolve(null);
    });
    req.on("timeout", () => { req.destroy(); resolve(null); });
  });
}
