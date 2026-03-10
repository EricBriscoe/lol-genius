import { describe, it, expect } from "vitest";
import { snapToSnapshot, parseLiveClientData, buildLiveFeatures, type GameState, type MomentumState } from "./features";
import { LIVE_FEATURE_NAMES, SNAPSHOT_SECONDS } from "./constants";

describe("snapToSnapshot", () => {
  it("snaps exactly to a snapshot boundary", () => {
    expect(snapToSnapshot(300)).toBe(300);
  });

  it("snaps to nearest when between two snapshots", () => {
    expect(snapToSnapshot(450)).toBe(300);
    expect(snapToSnapshot(451)).toBe(600);
  });

  it("clamps to max snapshot when above range", () => {
    expect(snapToSnapshot(3100)).toBe(3000);
  });

  it("clamps to min snapshot when below range", () => {
    expect(snapToSnapshot(0)).toBe(300);
    expect(snapToSnapshot(100)).toBe(300);
  });
});

describe("parseLiveClientData", () => {
  it("parses realistic game data with players and events", () => {
    const data = {
      allPlayers: [
        { summonerName: "Blue1", team: "ORDER", scores: { kills: 3, creepScore: 120 } },
        { summonerName: "Blue2", team: "ORDER", scores: { kills: 2, creepScore: 90 } },
        { summonerName: "Red1", team: "CHAOS", scores: { kills: 1, creepScore: 100 } },
        { summonerName: "Red2", team: "CHAOS", scores: { kills: 4, creepScore: 110 } },
      ],
      events: {
        Events: [
          { EventName: "FirstBlood", KillerName: "Blue1" },
          { EventName: "DragonKill", KillerName: "Blue2" },
          { EventName: "TurretKilled", KillerName: "Red1" },
          { EventName: "BaronKill", KillerName: "Blue1" },
          { EventName: "DragonKill", KillerName: "Red2", DragonType: "Elder" },
        ],
      },
      gameData: { gameTime: 1200, gameId: 42 },
    };

    const state = parseLiveClientData(data);
    expect(state.game_time).toBe(1200);
    expect(state.blue_kills).toBe(5);
    expect(state.red_kills).toBe(5);
    expect(state.kill_diff).toBe(0);
    expect(state.blue_cs).toBe(210);
    expect(state.red_cs).toBe(210);
    expect(state.blue_dragons).toBe(1);
    expect(state.red_dragons).toBe(0);
    expect(state.first_blood_blue).toBe(1);
    expect(state.blue_towers).toBe(0);
    expect(state.red_towers).toBe(1);
    expect(state.first_tower_blue).toBe(0);
    expect(state.blue_barons).toBe(1);
    expect(state.red_barons).toBe(0);
    expect(state.blue_elder).toBe(0);
    expect(state.red_elder).toBe(1);
    expect(state.first_dragon_blue).toBe(1);
    expect(state.dragon_diff).toBe(1);
    expect(state.elder_diff).toBe(-1);
  });

  it("counts herald and inhibitor events", () => {
    const data = {
      allPlayers: [
        { summonerName: "B1", team: "ORDER", scores: { kills: 0, creepScore: 0 } },
        { summonerName: "R1", team: "CHAOS", scores: { kills: 0, creepScore: 0 } },
      ],
      events: {
        Events: [
          { EventName: "HeraldKill", KillerName: "B1" },
          { EventName: "HeraldKill", KillerName: "R1" },
          { EventName: "InhibitorKilled", KillerName: "B1" },
        ],
      },
      gameData: { gameTime: 1500 },
    };
    const state = parseLiveClientData(data);
    expect(state.blue_heralds).toBe(1);
    expect(state.red_heralds).toBe(1);
    expect(state.blue_inhibitors).toBe(1);
    expect(state.red_inhibitors).toBe(0);
    expect(state.inhibitor_diff).toBe(1);
  });

  it("handles fully empty input object", () => {
    const state = parseLiveClientData({} as Parameters<typeof parseLiveClientData>[0]);
    expect(state.game_time).toBe(0);
    expect(state.blue_kills).toBe(0);
    expect(state.blue_dragons).toBe(0);
  });

  it("handles empty events gracefully", () => {
    const state = parseLiveClientData({
      allPlayers: [],
      events: { Events: [] },
      gameData: { gameTime: 600 },
    });
    expect(state.game_time).toBe(600);
    expect(state.blue_kills).toBe(0);
    expect(state.red_kills).toBe(0);
    expect(state.blue_dragons).toBe(0);
    expect(state.first_blood_blue).toBe(0);
  });
});

describe("buildLiveFeatures", () => {
  const baseState: GameState = {
    game_time: 900,
    blue_kills: 6, red_kills: 3, kill_diff: 3,
    blue_cs: 200, red_cs: 180, cs_diff: 20,
    blue_dragons: 1, red_dragons: 0, dragon_diff: 1,
    blue_barons: 0, red_barons: 0, baron_diff: 0,
    blue_towers: 2, red_towers: 1, tower_diff: 1,
    blue_heralds: 1, red_heralds: 0,
    blue_inhibitors: 0, red_inhibitors: 0, inhibitor_diff: 0,
    blue_elder: 0, red_elder: 0, elder_diff: 0,
    first_blood_blue: 1, first_tower_blue: 1, first_dragon_blue: 1,
    blue_avg_level: 6.0, red_avg_level: 5.0, blue_max_level: 7, red_max_level: 6,
  };

  const momentum: MomentumState = {
    prevDiffs: { kill_diff: 2, cs_diff: 15, tower_diff: 0 },
    peakKillDiff: 4,
    peakTowerDiff: 1,
    killDiffAccel: 0.5,
    recentKillShareDiff: 0.2,
  };

  it("produces output with all LIVE_FEATURE_NAMES keys", () => {
    const features = buildLiveFeatures(baseState, momentum);
    for (const name of LIVE_FEATURE_NAMES) {
      expect(features).toHaveProperty(name);
    }
    expect(Object.keys(features).length).toBe(LIVE_FEATURE_NAMES.length);
  });

  it("returns zero deltas when prevDiffs is null", () => {
    const noHistory: MomentumState = {
      prevDiffs: null,
      peakKillDiff: 0,
      peakTowerDiff: 0,
      killDiffAccel: 0,
      recentKillShareDiff: 0,
    };
    const features = buildLiveFeatures(baseState, noHistory);
    expect(features.kill_diff_delta).toBe(0);
    expect(features.cs_diff_delta).toBe(0);
    expect(features.tower_diff_delta).toBe(0);
  });

  it("guards against division by zero with small game time", () => {
    const earlyState: GameState = { ...baseState, game_time: 0 };
    const features = buildLiveFeatures(earlyState, momentum);
    expect(features.kill_rate_diff).toBeCloseTo(3.0);
  });

  it("computes derived momentum values correctly", () => {
    const features = buildLiveFeatures(baseState, momentum);
    expect(features.kill_diff_delta).toBe(1);
    expect(features.cs_diff_delta).toBe(5);
    expect(features.tower_diff_delta).toBe(1);
    expect(features.kill_lead_erosion).toBe(1);
    expect(features.tower_lead_erosion).toBe(0);
    expect(features.kill_diff_accel).toBe(0.5);
    expect(features.recent_kill_share_diff).toBe(0.2);
    expect(features.kill_rate_diff).toBeCloseTo(0.2);
  });

  it("uses raw game time not snapped", () => {
    const features = buildLiveFeatures(baseState, momentum);
    expect(features.game_time_seconds).toBe(900);
  });

  it("computes dragon soul features", () => {
    const soulState: GameState = { ...baseState, blue_dragons: 4, red_dragons: 3 };
    const features = buildLiveFeatures(soulState, momentum);
    expect(features.blue_has_soul).toBe(1.0);
    expect(features.red_has_soul).toBe(0.0);
    expect(features.blue_soul_point).toBe(1.0);
    expect(features.red_soul_point).toBe(1.0);
  });
});

describe("constants sanity", () => {
  it("LIVE_FEATURE_NAMES has expected count", () => {
    expect(LIVE_FEATURE_NAMES.length).toBe(72);
  });

  it("SNAPSHOT_SECONDS is sorted ascending", () => {
    for (let i = 1; i < SNAPSHOT_SECONDS.length; i++) {
      expect(SNAPSHOT_SECONDS[i]).toBeGreaterThan(SNAPSHOT_SECONDS[i - 1]);
    }
  });
});
