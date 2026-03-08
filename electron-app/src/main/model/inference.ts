import * as ort from "onnxruntime-node";
import { readFileSync, existsSync } from "fs";
import { join } from "path";
import { calibrate, type Calibrator } from "./calibrator";
import log from "../log";

const logger = log.scope("inference");

interface ModelState {
  session: ort.InferenceSession;
  featureNames: string[];
  calibrator: Calibrator | null;
  featureImportance: { feature: string; importance: number }[];
  modelDir: string;
}

const models = new Map<string, ModelState>();

export async function loadModel(modelDir: string, modelType = "live"): Promise<void> {
  const existing = models.get(modelType);
  if (existing?.modelDir === modelDir) return;

  const onnxPath = join(modelDir, "model.onnx");
  if (!existsSync(onnxPath)) {
    throw new Error(`Model not found at ${onnxPath}`);
  }

  const session = await ort.InferenceSession.create(onnxPath);

  const namesPath = join(modelDir, "feature_names.json");
  const featureNames: string[] = JSON.parse(readFileSync(namesPath, "utf-8"));

  const calPath = join(modelDir, "calibrator.json");
  const calibrator: Calibrator | null = existsSync(calPath)
    ? JSON.parse(readFileSync(calPath, "utf-8"))
    : null;

  const impPath = join(modelDir, "feature_importance.json");
  const featureImportance: { feature: string; importance: number }[] = existsSync(impPath)
    ? JSON.parse(readFileSync(impPath, "utf-8"))
    : [];

  models.set(modelType, { session, featureNames, calibrator, featureImportance, modelDir });
  logger.debug(`Loaded ${modelType} model from`, modelDir, "features:", featureNames.length, "calibrator:", !!calibrator);
}

export function isModelLoaded(modelType = "live"): boolean {
  return models.has(modelType);
}

export function getFeatureNames(modelType = "live"): string[] {
  return models.get(modelType)?.featureNames ?? [];
}

export function getFeatureImportance(modelType = "live"): { feature: string; importance: number }[] {
  return models.get(modelType)?.featureImportance ?? [];
}

export async function predict(features: Record<string, number>, modelType = "live"): Promise<number> {
  const model = models.get(modelType);
  if (!model) throw new Error(`Model "${modelType}" not loaded`);

  const values = new Float32Array(model.featureNames.length);
  for (let i = 0; i < model.featureNames.length; i++) {
    values[i] = features[model.featureNames[i]] ?? 0.0;
  }

  logger.debug(`${modelType} inference:`, model.featureNames.length, "features");
  const tensor = new ort.Tensor("float32", values, [1, model.featureNames.length]);
  const inputName = model.session.inputNames[0];
  const results = await model.session.run({ [inputName]: tensor });

  const outputName = model.session.outputNames[0];
  const output = results[outputName];

  let prob: number;
  if (output.dims.length === 2 && output.dims[1] === 2) {
    prob = (output.data as Float32Array)[1];
  } else {
    prob = (output.data as Float32Array)[0];
  }

  if (model.calibrator) {
    prob = calibrate(prob, model.calibrator);
  }

  return prob;
}
