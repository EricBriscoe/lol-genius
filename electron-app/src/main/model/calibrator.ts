export interface IsotonicCalibrator {
  x_thresholds: number[];
  y_thresholds: number[];
}

export interface PlattCalibrator {
  method: "platt";
  a: number;
  b: number;
}

export type Calibrator = IsotonicCalibrator | PlattCalibrator;

export function calibrate(prob: number, cal: Calibrator): number {
  if ("method" in cal && cal.method === "platt") {
    return 1.0 / (1.0 + Math.exp(-(cal.a * prob + cal.b)));
  }

  const { x_thresholds: xs, y_thresholds: ys } = cal as IsotonicCalibrator;
  if (xs.length === 0) return prob;
  if (prob <= xs[0]) return ys[0];
  if (prob >= xs[xs.length - 1]) return ys[ys.length - 1];

  for (let i = 1; i < xs.length; i++) {
    if (prob <= xs[i]) {
      const t = (prob - xs[i - 1]) / (xs[i] - xs[i - 1]);
      return ys[i - 1] + t * (ys[i] - ys[i - 1]);
    }
  }
  return ys[ys.length - 1];
}
