import { readdirSync, readFileSync, writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";
import https from "https";
import log from "../log";

const logger = log.scope("ddragon");

const AP_TAGS = new Set(["Mage", "Support"]);
const AD_TAGS = new Set(["Fighter", "Assassin", "Marksman"]);

export interface ChampionData {
  id: string;
  name: string;
  key: number;
  tags: string[];
  stats: Record<string, number>;
  info: Record<string, number>;
}

let champions: Record<number, ChampionData> = {};
let loadedVersion = "";

export function isLoaded(): boolean {
  return Object.keys(champions).length > 0;
}

export function loadChampionData(resourcesPath: string): Record<number, ChampionData> {
  if (isLoaded()) return champions;

  const ddragonDir = join(resourcesPath, "ddragon");
  let files: string[];
  try {
    files = readdirSync(ddragonDir).filter((f) => f.startsWith("champions_") && f.endsWith(".json"));
  } catch {
    logger.warn("No ddragon directory found at", ddragonDir);
    return champions;
  }

  if (files.length === 0) {
    logger.warn("No champion data files found in", ddragonDir);
    return champions;
  }

  files.sort();
  const latest = files[files.length - 1];
  loadedVersion = latest.replace("champions_", "").replace(".json", "");

  const raw = JSON.parse(readFileSync(join(ddragonDir, latest), "utf-8"));
  champions = {};
  for (const [k, v] of Object.entries(raw)) {
    champions[parseInt(k, 10)] = v as ChampionData;
  }
  logger.debug("Loaded", Object.keys(champions).length, "champions from", latest);
  return champions;
}

function httpsGetJson(url: string, maxRedirects = 5): Promise<unknown> {
  return new Promise((resolve, reject) => {
    if (maxRedirects <= 0) { reject(new Error("Too many redirects")); return; }
    https.get(url, { headers: { "User-Agent": "lol-genius-electron" }, timeout: 15_000 }, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume();
        httpsGetJson(res.headers.location, maxRedirects - 1).then(resolve, reject);
        return;
      }
      if (!res.statusCode || res.statusCode < 200 || res.statusCode >= 300) {
        res.resume();
        reject(new Error(`HTTP ${res.statusCode} for ${url}`));
        return;
      }
      let body = "";
      res.on("data", (chunk: Buffer) => { body += chunk.toString(); });
      res.on("end", () => {
        try { resolve(JSON.parse(body)); }
        catch (e) { reject(e); }
      });
      res.on("error", reject);
    }).on("error", reject);
  });
}

export async function downloadChampionData(saveDir: string): Promise<void> {
  logger.info("Downloading champion data from CDN...");

  const versions = await httpsGetJson("https://ddragon.leagueoflegends.com/api/versions.json") as string[];
  const ver = versions[0];

  const raw = await httpsGetJson(`https://ddragon.leagueoflegends.com/cdn/${ver}/data/en_US/champion.json`) as { data: Record<string, Record<string, unknown>> };

  const result: Record<string, ChampionData> = {};
  for (const champ of Object.values(raw.data)) {
    const key = parseInt(champ.key as string, 10);
    result[String(key)] = {
      id: champ.id as string,
      name: champ.name as string,
      key,
      tags: (champ.tags ?? []) as string[],
      stats: (champ.stats ?? {}) as Record<string, number>,
      info: (champ.info ?? {}) as Record<string, number>,
    };
  }

  mkdirSync(saveDir, { recursive: true });
  const outPath = join(saveDir, `champions_${ver}.json`);
  writeFileSync(outPath, JSON.stringify(result));
  logger.info(`Saved ${Object.keys(result).length} champions for patch ${ver}`);

  champions = {};
  for (const [k, v] of Object.entries(result)) {
    champions[parseInt(k, 10)] = v;
  }
  loadedVersion = ver;
}

export function getChampionVersion(): string {
  return loadedVersion;
}

export function getChampion(id: number): ChampionData | null {
  return champions[id] ?? null;
}

export function classifyDamageType(id: number): "AP" | "AD" | "MIXED" {
  const champ = getChampion(id);
  if (!champ) return "AD";
  const tags = new Set(champ.tags);
  const hasAp = [...tags].some((t) => AP_TAGS.has(t));
  const hasAd = [...tags].some((t) => AD_TAGS.has(t));
  if (hasAp && hasAd) return "MIXED";
  if (hasAp) return "AP";
  return "AD";
}

export function getAttackRange(id: number): number {
  const champ = getChampion(id);
  return champ?.stats?.attackrange ?? 550;
}

export function isMelee(id: number): boolean {
  return getAttackRange(id) <= 200;
}

export function getChampionName(id: number): string {
  return getChampion(id)?.name ?? `Champion ${id}`;
}

export function getChampionInternalName(id: number): string {
  return getChampion(id)?.id ?? "";
}
