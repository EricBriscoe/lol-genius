import { describe, it, expect } from "vitest";
import { calibrate, type Calibrator } from "./calibrator";

describe("calibrate", () => {
  const cal: Calibrator = {
    x_thresholds: [0.2, 0.4, 0.6, 0.8],
    y_thresholds: [0.1, 0.35, 0.65, 0.9],
  };

  it("returns prob unchanged when thresholds are empty", () => {
    expect(calibrate(0.7, { x_thresholds: [], y_thresholds: [] })).toBe(0.7);
  });

  it("returns first y value when below min threshold", () => {
    expect(calibrate(0.05, cal)).toBe(0.1);
  });

  it("returns last y value when above max threshold", () => {
    expect(calibrate(0.95, cal)).toBe(0.9);
  });

  it("interpolates correctly in mid-range", () => {
    // prob = 0.3 is midpoint of [0.2, 0.4] → midpoint of [0.1, 0.35] = 0.225
    expect(calibrate(0.3, cal)).toBeCloseTo(0.225);
    // prob = 0.5 is midpoint of [0.4, 0.6] → midpoint of [0.35, 0.65] = 0.5
    expect(calibrate(0.5, cal)).toBeCloseTo(0.5);
  });
});
