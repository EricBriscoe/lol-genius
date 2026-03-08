import * as ort from "onnxruntime-node";
import { readFileSync, existsSync } from "fs";
import { join } from "path";
import { calibrate, type Calibrator } from "./calibrator";
import log from "../log";

const logger = log.scope("inference");

let session: ort.InferenceSession | null = null;
let featureNames: string[] = [];
let calibrator: Calibrator | null = null;
let featureImportance: { feature: string; importance: number }[] = [];
let loadedModelDir: string | null = null;

export async function loadModel(modelDir: string): Promise<void> {
  if (loadedModelDir === modelDir && session) return;

  const onnxPath = join(modelDir, "model.onnx");
  if (!existsSync(onnxPath)) {
    throw new Error(`Model not found at ${onnxPath}`);
  }

  session = await ort.InferenceSession.create(onnxPath);

  const namesPath = join(modelDir, "feature_names.json");
  featureNames = JSON.parse(readFileSync(namesPath, "utf-8"));

  const calPath = join(modelDir, "calibrator.json");
  calibrator = existsSync(calPath)
    ? JSON.parse(readFileSync(calPath, "utf-8"))
    : null;

  const impPath = join(modelDir, "feature_importance.json");
  featureImportance = existsSync(impPath)
    ? JSON.parse(readFileSync(impPath, "utf-8"))
    : [];

  loadedModelDir = modelDir;
  logger.debug("Loaded model from", modelDir, "features:", featureNames.length, "calibrator:", !!calibrator);
}

export function getFeatureNames(): string[] {
  return featureNames;
}

export function getFeatureImportance(): { feature: string; importance: number }[] {
  return featureImportance;
}

export async function predict(features: Record<string, number>): Promise<number> {
  if (!session) throw new Error("Model not loaded");

  const values = new Float32Array(featureNames.length);
  for (let i = 0; i < featureNames.length; i++) {
    values[i] = features[featureNames[i]] ?? 0.0;
  }

  logger.debug("Inference input:", featureNames.length, "features");
  const tensor = new ort.Tensor("float32", values, [1, featureNames.length]);
  const inputName = session.inputNames[0];
  const results = await session.run({ [inputName]: tensor });

  const outputName = session.outputNames[0];
  const output = results[outputName];

  let prob: number;
  if (output.dims.length === 2 && output.dims[1] === 2) {
    prob = (output.data as Float32Array)[1];
  } else {
    prob = (output.data as Float32Array)[0];
  }

  if (calibrator) {
    prob = calibrate(prob, calibrator);
  }

  return prob;
}
