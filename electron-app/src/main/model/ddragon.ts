import { readdirSync, readFileSync } from "fs";
import { join } from "path";
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

export function loadChampionData(resourcesPath: string): Record<number, ChampionData> {
  if (Object.keys(champions).length > 0) return champions;

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
