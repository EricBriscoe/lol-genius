import { describe, it, expect, beforeAll } from "vitest";
import {
  extractChampionFeatures,
  extractPlayerFeatures,
  extractTeamFeatures,
  extractDraftFeatures,
  extractInteractionFeatures,
  buildPregameFeatures,
} from "./pregame-features";
import { ALL_TAGS } from "./pregame-constants";
import type { ChampSelectSession } from "../lcu-client/types";

describe("extractChampionFeatures", () => {
  it("returns default features for unknown champion", () => {
    const features = extractChampionFeatures(0);
    expect(features.champ_hp_base).toBe(580.0);
    expect(features.champ_ad_base).toBe(60.0);
    expect(features.is_ap_champ).toBe(0.0);
    expect(features.is_melee).toBe(0.0);
    expect(features.tag_fighter).toBe(0.0);
    expect(features.tag_mage).toBe(0.0);

    const featureCount = Object.keys(features).length;
    expect(featureCount).toBe(20);
  });

  it("returns correct number of features", () => {
    const features = extractChampionFeatures(999999);
    const keys = Object.keys(features);
    expect(keys).toContain("champ_hp_base");
    expect(keys).toContain("champ_attack_range");
    expect(keys).toContain("is_ap_champ");
    expect(keys).toContain("is_melee");
    for (const tag of ALL_TAGS) {
      expect(keys).toContain(`tag_${tag.toLowerCase()}`);
    }
  });
});

describe("extractPlayerFeatures", () => {
  it("returns defaults when no opts provided", () => {
    const features = extractPlayerFeatures();
    expect(features.rank_numeric).toBe(12.0);
    expect(features.ranked_winrate).toBe(0.5);
    expect(features.recent_winrate).toBe(0.5);
    expect(features.avg_kda).toBe(2.0);
    expect(features.mastery_points).toBe(0.0);
    expect(features.flash_on_d).toBe(0.0);
    expect(Object.keys(features).length).toBe(52);
  });

  it("populates rank fields from opts", () => {
    const features = extractPlayerFeatures({
      rankedTier: "DIAMOND",
      rankedDivision: "II",
      rankedLP: 50,
      rankedWins: 100,
      rankedLosses: 80,
    });
    expect(features.rank_numeric).toBeCloseTo(26.5, 1);
    expect(features.ranked_games).toBe(180);
    expect(features.ranked_winrate).toBeGreaterThan(0.5);
  });

  it("populates spell features", () => {
    const features = extractPlayerFeatures({ spell1Id: 4, spell2Id: 14 });
    expect(features.flash_on_d).toBe(1.0);
    expect(features.has_ignite).toBe(1.0);
    expect(features.has_teleport).toBe(0.0);
  });
});

describe("extractTeamFeatures", () => {
  it("aggregates player and champion features", () => {
    const playerFeats = Array.from({ length: 5 }, () => ({
      rank_numeric: 12.0,
      recent_winrate: 0.5,
      mastery_points: 0,
      is_autofill: 0,
      summoner_level: 0,
      hot_streak: 0,
      avg_wards_placed: 0,
      avg_cc_score: 0,
    }));
    const champFeats = Array.from({ length: 5 }, () => ({
      is_ap_champ: 0,
      is_mixed_champ: 0,
      is_melee: 1,
      tag_tank: 1,
      tag_assassin: 0,
      tag_mage: 0,
      tag_marksman: 0,
      tag_support: 0,
      champ_attack_score: 5,
      champ_defense_score: 5,
      champ_magic_score: 5,
      champ_difficulty: 5,
    }));

    const features = extractTeamFeatures(playerFeats, champFeats);
    expect(features.avg_rank).toBe(12.0);
    expect(features.rank_spread).toBe(0.0);
    expect(features.melee_count).toBe(5);
    expect(features.tank_count).toBe(5);
    expect(features.ad_ratio).toBe(1.0);
    expect(Object.keys(features).length).toBe(22);
  });
});

describe("extractDraftFeatures", () => {
  it("computes per-position diffs", () => {
    const blueFeats: Record<string, Record<string, number>> = {
      TOP: { rank_numeric: 16.0, mastery_points: 50000, recent_winrate: 0.6, champ_winrate: 0.55, summoner_level: 100, winrate_rank_residual: 0.05 },
    };
    const redFeats: Record<string, Record<string, number>> = {
      TOP: { rank_numeric: 12.0, mastery_points: 30000, recent_winrate: 0.5, champ_winrate: 0.5, summoner_level: 80, winrate_rank_residual: 0.0 },
    };

    const features = extractDraftFeatures(blueFeats, redFeats);
    expect(features.top_rank_diff).toBe(4.0);
    expect(features.top_mastery_diff).toBe(20000);
    expect(features.top_wr_diff).toBeCloseTo(0.1);
    expect(Object.keys(features).length).toBe(30);
  });

  it("defaults cancel out to 0 for missing positions", () => {
    const features = extractDraftFeatures({}, {});
    expect(features.top_rank_diff).toBe(0.0);
    expect(features.jg_wr_diff).toBe(0.0);
  });
});

describe("extractInteractionFeatures", () => {
  it("returns correct number of features", () => {
    const blueByPos: Record<string, { championId: number }> = {};
    const redByPos: Record<string, { championId: number }> = {};
    const blueChampFeats = Array.from({ length: 5 }, () => ({}));
    const redChampFeats = Array.from({ length: 5 }, () => ({}));

    const features = extractInteractionFeatures(blueByPos, redByPos, blueChampFeats, redChampFeats);
    expect(Object.keys(features).length).toBe(25);
    expect(features.team_ap_diff).toBeDefined();
    expect(features.frontline_diff).toBeDefined();
  });
});

describe("buildPregameFeatures", () => {
  it("produces features from a minimal session", () => {
    const session: ChampSelectSession = {
      myTeam: [
        { summonerId: 1, championId: 266, assignedPosition: "top", spell1Id: 4, spell2Id: 12, team: 1 },
        { summonerId: 2, championId: 64, assignedPosition: "jungle", spell1Id: 11, spell2Id: 4, team: 1 },
        { summonerId: 3, championId: 103, assignedPosition: "middle", spell1Id: 4, spell2Id: 14, team: 1 },
        { summonerId: 4, championId: 222, assignedPosition: "bottom", spell1Id: 7, spell2Id: 4, team: 1 },
        { summonerId: 5, championId: 412, assignedPosition: "utility", spell1Id: 4, spell2Id: 3, team: 1 },
      ],
      theirTeam: [
        { summonerId: 6, championId: 86, assignedPosition: "top", spell1Id: 4, spell2Id: 14, team: 2 },
        { summonerId: 7, championId: 121, assignedPosition: "jungle", spell1Id: 11, spell2Id: 4, team: 2 },
        { summonerId: 8, championId: 238, assignedPosition: "middle", spell1Id: 4, spell2Id: 14, team: 2 },
        { summonerId: 9, championId: 51, assignedPosition: "bottom", spell1Id: 4, spell2Id: 7, team: 2 },
        { summonerId: 10, championId: 267, assignedPosition: "utility", spell1Id: 4, spell2Id: 3, team: 2 },
      ],
      bans: { myTeamBans: [157, 236, 39], theirTeamBans: [92, 55, 24] },
      timer: { phase: "FINALIZATION", adjustedTimeLeftInPhase: 15000 },
      localPlayerCellId: 0,
    };

    const features = buildPregameFeatures(session);
    expect(features.patch_numeric).toBeDefined();
    expect(features.blue_bans_count).toBe(3);
    expect(features.red_bans_count).toBe(3);

    const keys = Object.keys(features);
    expect(keys.length).toBeGreaterThan(100);

    expect(keys.some((k) => k.startsWith("blue_top_"))).toBe(true);
    expect(keys.some((k) => k.startsWith("red_sup_"))).toBe(true);
    expect(keys).toContain("blue_avg_rank");
    expect(keys).toContain("red_avg_rank");
    expect(keys).toContain("top_rank_diff");
    expect(keys).toContain("team_ap_diff");
  });

  it("applies defaults for empty features", () => {
    const session: ChampSelectSession = {
      myTeam: [
        { summonerId: 1, championId: 0, assignedPosition: "top", spell1Id: 0, spell2Id: 0, team: 1 },
        { summonerId: 2, championId: 0, assignedPosition: "jungle", spell1Id: 0, spell2Id: 0, team: 1 },
        { summonerId: 3, championId: 0, assignedPosition: "middle", spell1Id: 0, spell2Id: 0, team: 1 },
        { summonerId: 4, championId: 0, assignedPosition: "bottom", spell1Id: 0, spell2Id: 0, team: 1 },
        { summonerId: 5, championId: 0, assignedPosition: "utility", spell1Id: 0, spell2Id: 0, team: 1 },
      ],
      theirTeam: [
        { summonerId: 6, championId: 0, assignedPosition: "top", spell1Id: 0, spell2Id: 0, team: 2 },
        { summonerId: 7, championId: 0, assignedPosition: "jungle", spell1Id: 0, spell2Id: 0, team: 2 },
        { summonerId: 8, championId: 0, assignedPosition: "middle", spell1Id: 0, spell2Id: 0, team: 2 },
        { summonerId: 9, championId: 0, assignedPosition: "bottom", spell1Id: 0, spell2Id: 0, team: 2 },
        { summonerId: 10, championId: 0, assignedPosition: "utility", spell1Id: 0, spell2Id: 0, team: 2 },
      ],
      bans: { myTeamBans: [], theirTeamBans: [] },
      timer: { phase: "PLANNING", adjustedTimeLeftInPhase: 30000 },
      localPlayerCellId: 0,
    };

    const features = buildPregameFeatures(session);
    expect(features.blue_top_rank_numeric).toBe(12.0);
    expect(features.top_rank_diff).toBe(0.0);
  });
});
