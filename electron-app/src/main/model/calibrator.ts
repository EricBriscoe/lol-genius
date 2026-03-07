export interface Calibrator {
  x_thresholds: number[];
  y_thresholds: number[];
}

export function calibrate(prob: number, cal: Calibrator): number {
  const { x_thresholds: xs, y_thresholds: ys } = cal;
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
