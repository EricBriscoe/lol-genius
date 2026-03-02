import type {
  StatusData,
  DistributionData,
  ModelRun,
  TrainingRequest,
  TrainingStatus,
  PredictLookup,
  PredictResult,
  LiveGameStatus,
} from "./types";

const BASE = "/api/v1";

async function parseErrorBody(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.error || body.detail || `${res.status} ${res.statusText}`;
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(await parseErrorBody(res));
  return res.json();
}

export const fetchStatus = () => get<StatusData>("/status");
export const fetchDistributions = () => get<DistributionData>("/distributions");
export const fetchModelRuns = (modelType?: string) =>
  get<ModelRun[]>(modelType ? `/model/runs?model_type=${modelType}` : "/model/runs");
export const fetchModelRun = (id: string) => get<ModelRun>(`/model/runs/${id}`);
export async function triggerTraining(req: TrainingRequest = {}) {
  const res = await fetch(`${BASE}/model/train`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await parseErrorBody(res));
  return res.json();
}

export const fetchPresets = () =>
  get<Record<string, Record<string, number | string>>>("/model/presets");

export const fetchTrainingStatus = () =>
  get<TrainingStatus & { stage: string }>("/model/training-status");

export const lookupPlayer = (gameName: string, tagLine: string) =>
  get<PredictLookup>(`/predict/lookup?game_name=${encodeURIComponent(gameName)}&tag_line=${encodeURIComponent(tagLine)}`);

export async function predictLiveGame(gameData: unknown): Promise<PredictResult> {
  const res = await fetch(`${BASE}/predict/live`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_data: gameData }),
  });
  if (!res.ok) throw new Error(await parseErrorBody(res));
  return res.json();
}

export async function startLiveGame(host: string, port: number): Promise<void> {
  const res = await fetch(`${BASE}/live-game/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host, port }),
  });
  if (!res.ok) throw new Error(await parseErrorBody(res));
}

export async function stopLiveGame(): Promise<void> {
  const res = await fetch(`${BASE}/live-game/stop`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseErrorBody(res));
}

export const fetchLiveGameStatus = () => get<LiveGameStatus>("/live-game/status");

export async function buildTimelinesFromDb(): Promise<{ saved: number }> {
  const res = await fetch(`${BASE}/timelines/build-from-db`, { method: "POST" });
  if (!res.ok) throw new Error(await parseErrorBody(res));
  return res.json();
}

export const fetchCrawlerMode = () => get<{ mode: string }>("/crawler/mode");

export async function setCrawlerMode(mode: "crawl" | "fetch_timelines"): Promise<void> {
  const res = await fetch(`${BASE}/crawler/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  if (!res.ok) throw new Error(await parseErrorBody(res));
}
