import type {
  StatusData,
  DistributionData,
  ModelRun,
  PredictLookup,
  PredictResult,
} from "./types";

const BASE = "/api/v1";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const fetchStatus = () => get<StatusData>("/status");
export const fetchDistributions = () => get<DistributionData>("/distributions");
export const fetchModelRuns = () => get<ModelRun[]>("/model/runs");
export const fetchModelRun = (id: string) => get<ModelRun>(`/model/runs/${id}`);
export async function triggerTraining(notes?: string) {
  const res = await fetch(`${BASE}/model/train`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes: notes || "" }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const lookupPlayer = (gameName: string, tagLine: string) =>
  get<PredictLookup>(`/predict/lookup?game_name=${encodeURIComponent(gameName)}&tag_line=${encodeURIComponent(tagLine)}`);

export async function predictLiveGame(gameData: unknown): Promise<PredictResult> {
  const res = await fetch(`${BASE}/predict/live`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_data: gameData }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `${res.status} ${res.statusText}`);
  }
  return res.json();
}
