import type { ChampSelectSession, RankedStats } from "../lcu-client/types";
import * as ddragon from "./ddragon";
import {
  POSITION_ORDER,
  POSITION_SHORT,
  TIER_MAP,
  DIV_MAP,
  FLASH_ID,
  SPELL_MAP,
  ALL_TAGS,
  TAG_ADVANTAGE,
  DEFAULT_PLAYER_FEATURES,
  SMURF_WR_RESIDUAL_WEIGHT,
  SMURF_RANK_MISMATCH_WEIGHT,
  SMURF_GAMES_PER_LEVEL_WEIGHT,
  SMURF_RANK_PER_GAME_WEIGHT,
} from "./pregame-constants";

function rankToNumeric(tier: string, division: string, lp: number): number {
  const base = TIER_MAP[tier] ?? 12;
  const divOffset = DIV_MAP[division] ?? 0;
  return base + divOffset + lp / 100.0;
}

export function extractChampionFeatures(championId: number): Record<string, number> {
  const champ = ddragon.getChampion(championId);
  const features: Record<string, number> = {};

  if (!champ) {
    features.champ_hp_base = 580.0;
    features.champ_ad_base = 60.0;
    features.champ_armor_base = 33.0;
    features.champ_mr_base = 32.0;
    features.champ_attack_range = 550.0;
    features.champ_hp_per_level = 90.0;
    features.champ_ad_per_level = 3.0;
    features.is_ap_champ = 0.0;
    features.is_mixed_champ = 0.0;
    features.is_melee = 0.0;
    features.champ_attack_score = 5.0;
    features.champ_defense_score = 5.0;
    features.champ_magic_score = 5.0;
    features.champ_difficulty = 5.0;
    for (const tag of ALL_TAGS) {
      features[`tag_${tag.toLowerCase()}`] = 0.0;
    }
    return features;
  }

  const stats = champ.stats ?? {};
  features.champ_hp_base = stats.hp ?? 580;
  features.champ_ad_base = stats.attackdamage ?? 60;
  features.champ_armor_base = stats.armor ?? 33;
  features.champ_mr_base = stats.spellblock ?? 32;
  features.champ_attack_range = stats.attackrange ?? 550;
  features.champ_hp_per_level = stats.hpperlevel ?? 90;
  features.champ_ad_per_level = stats.attackdamageperlevel ?? 3;

  const dmgType = ddragon.classifyDamageType(championId);
  features.is_ap_champ = dmgType === "AP" ? 1.0 : 0.0;
  features.is_mixed_champ = dmgType === "MIXED" ? 1.0 : 0.0;
  features.is_melee = ddragon.isMelee(championId) ? 1.0 : 0.0;

  const info = champ.info ?? {};
  features.champ_attack_score = info.attack ?? 5;
  features.champ_defense_score = info.defense ?? 5;
  features.champ_magic_score = info.magic ?? 5;
  features.champ_difficulty = info.difficulty ?? 5;

  const tags = new Set(champ.tags ?? []);
  for (const tag of ALL_TAGS) {
    features[`tag_${tag.toLowerCase()}`] = tags.has(tag) ? 1.0 : 0.0;
  }

  return features;
}

interface PlayerFeatureOpts {
  spell1Id?: number;
  spell2Id?: number;
  rankedTier?: string;
  rankedDivision?: string;
  rankedLP?: number;
  rankedWins?: number;
  rankedLosses?: number;
}

export function extractPlayerFeatures(opts?: PlayerFeatureOpts): Record<string, number> {
  const features = { ...DEFAULT_PLAYER_FEATURES };

  if (opts?.rankedTier) {
    features.rank_numeric = rankToNumeric(
      opts.rankedTier,
      opts.rankedDivision ?? "IV",
      opts.rankedLP ?? 0,
    );
    features.league_points = opts.rankedLP ?? 0;

    const totalGames = (opts.rankedWins ?? 0) + (opts.rankedLosses ?? 0);
    features.ranked_games = totalGames;
    if (totalGames > 0) {
      features.ranked_winrate =
        ((opts.rankedWins ?? 0) + 10 * 0.5) / (totalGames + 10);
    }

    const rn = features.rank_numeric;
    const wr = features.ranked_winrate;
    const rg = features.ranked_games;
    const sl = features.summoner_level;
    const expectedWr = 0.45 + (rn / 30.0) * 0.1;
    features.winrate_rank_residual = wr - expectedWr;
    features.games_per_level = rg / Math.max(sl, 1.0);
    features.rank_per_game = rn / Math.max(rg, 1.0);
    const expectedRank = Math.min((sl / 500.0) * 30.0, 30.0);
    features.level_rank_mismatch = rn - expectedRank;
    features.smurf_score =
      Math.max(features.winrate_rank_residual, 0) * SMURF_WR_RESIDUAL_WEIGHT +
      Math.max(features.level_rank_mismatch, 0) * SMURF_RANK_MISMATCH_WEIGHT +
      Math.min(features.games_per_level, 1.0) * SMURF_GAMES_PER_LEVEL_WEIGHT +
      Math.min(features.rank_per_game, 1.0) * SMURF_RANK_PER_GAME_WEIGHT;
  }

  if (opts?.spell1Id != null || opts?.spell2Id != null) {
    const s1 = opts?.spell1Id ?? 0;
    const s2 = opts?.spell2Id ?? 0;
    features.flash_on_d = s1 === FLASH_ID ? 1.0 : 0.0;
    for (const [idStr, featName] of Object.entries(SPELL_MAP)) {
      const spellId = parseInt(idStr, 10);
      features[featName] = s1 === spellId || s2 === spellId ? 1.0 : 0.0;
    }
  }

  return features;
}

export function extractTeamFeatures(
  playerFeats: Record<string, number>[],
  champFeats: Record<string, number>[],
): Record<string, number> {
  const features: Record<string, number> = {};
  const n = Math.max(playerFeats.length, 1);
  const nChamps = Math.max(champFeats.length, 1);

  const ranks = playerFeats.map((pf) => pf.rank_numeric ?? 12.0);
  features.avg_rank = ranks.reduce((a, b) => a + b, 0) / n;
  if (ranks.length > 1) {
    const mean = features.avg_rank;
    features.rank_spread = Math.sqrt(
      ranks.reduce((s, r) => s + (r - mean) ** 2, 0) / ranks.length,
    );
  } else {
    features.rank_spread = 0.0;
  }

  features.avg_team_winrate =
    playerFeats.reduce((s, pf) => s + (pf.recent_winrate ?? 0.5), 0) / n;
  features.avg_mastery =
    playerFeats.reduce((s, pf) => s + (pf.mastery_points ?? 0), 0) / n;

  let adCount = 0, apCount = 0, mixedCount = 0;
  for (const cf of champFeats) {
    if ((cf.is_ap_champ ?? 0) > 0.5) apCount++;
    else if ((cf.is_mixed_champ ?? 0) > 0.5) mixedCount++;
    else adCount++;
  }
  const total = Math.max(champFeats.length, 1);
  features.ad_ratio = adCount / total;
  features.ap_ratio = apCount / total;

  const ratios = [adCount / total, apCount / total, mixedCount / total];
  features.damage_diversity = -ratios.reduce(
    (s, r) => s + (r > 0 ? r * Math.log2(r) : 0), 0,
  );

  features.melee_count = champFeats.filter((cf) => (cf.is_melee ?? 0) > 0.5).length;
  features.tank_count = champFeats.filter((cf) => (cf.tag_tank ?? 0) > 0.5).length;
  features.assassin_count = champFeats.filter((cf) => (cf.tag_assassin ?? 0) > 0.5).length;
  features.mage_count = champFeats.filter((cf) => (cf.tag_mage ?? 0) > 0.5).length;
  features.marksman_count = champFeats.filter((cf) => (cf.tag_marksman ?? 0) > 0.5).length;
  features.support_count = champFeats.filter((cf) => (cf.tag_support ?? 0) > 0.5).length;
  features.autofill_count = playerFeats.filter((pf) => (pf.is_autofill ?? 0) > 0.5).length;

  features.avg_summoner_level =
    playerFeats.reduce((s, pf) => s + (pf.summoner_level ?? 0), 0) / n;
  features.hot_streak_count = playerFeats.filter((pf) => (pf.hot_streak ?? 0) > 0.5).length;
  features.avg_wards_placed =
    playerFeats.reduce((s, pf) => s + (pf.avg_wards_placed ?? 0), 0) / n;
  features.avg_cc_score =
    playerFeats.reduce((s, pf) => s + (pf.avg_cc_score ?? 0), 0) / n;

  features.total_attack_score = champFeats.reduce(
    (s, cf) => s + (cf.champ_attack_score ?? 5), 0,
  );
  features.total_defense_score = champFeats.reduce(
    (s, cf) => s + (cf.champ_defense_score ?? 5), 0,
  );
  features.total_magic_score = champFeats.reduce(
    (s, cf) => s + (cf.champ_magic_score ?? 5), 0,
  );
  features.avg_difficulty = champFeats.reduce(
    (s, cf) => s + (cf.champ_difficulty ?? 5), 0,
  ) / nChamps;

  return features;
}

export function extractDraftFeatures(
  bluePlayerFeats: Record<string, Record<string, number>>,
  redPlayerFeats: Record<string, Record<string, number>>,
): Record<string, number> {
  const features: Record<string, number> = {};

  for (const pos of POSITION_ORDER) {
    const short = POSITION_SHORT[pos];
    const bp = bluePlayerFeats[pos] ?? {};
    const rp = redPlayerFeats[pos] ?? {};

    features[`${short}_rank_diff`] = (bp.rank_numeric ?? 12.0) - (rp.rank_numeric ?? 12.0);
    features[`${short}_mastery_diff`] = (bp.mastery_points ?? 0) - (rp.mastery_points ?? 0);
    features[`${short}_wr_diff`] = (bp.recent_winrate ?? 0.5) - (rp.recent_winrate ?? 0.5);
    features[`${short}_champ_wr_diff`] = (bp.champ_winrate ?? 0.5) - (rp.champ_winrate ?? 0.5);
    features[`${short}_summoner_level_diff`] = (bp.summoner_level ?? 0) - (rp.summoner_level ?? 0);
    features[`${short}_wr_residual_diff`] = (bp.winrate_rank_residual ?? 0) - (rp.winrate_rank_residual ?? 0);
  }

  return features;
}

function tagAdvantageScore(blueTags: string[], redTags: string[]): number {
  let score = 0.0;
  for (const bt of blueTags) {
    for (const rt of redTags) {
      score += TAG_ADVANTAGE[`${bt}:${rt}`] ?? -(TAG_ADVANTAGE[`${rt}:${bt}`] ?? 0.0);
    }
  }
  return score;
}

function shannonEntropy(counts: number[]): number {
  const total = counts.reduce((a, b) => a + b, 0);
  if (total === 0) return 0.0;
  let entropy = 0.0;
  for (const c of counts) {
    if (c > 0) {
      const p = c / total;
      entropy -= p * Math.log2(p);
    }
  }
  return entropy;
}

export function extractInteractionFeatures(
  blueByPos: Record<string, { championId: number }>,
  redByPos: Record<string, { championId: number }>,
  blueChampFeats: Record<string, number>[],
  redChampFeats: Record<string, number>[],
): Record<string, number> {
  const features: Record<string, number> = {};

  let blueAp = 0, blueAd = 0, redAp = 0, redAd = 0;
  let blueArmorSum = 0, redArmorSum = 0;
  const blueTagsCount: Record<string, number> = {};
  const redTagsCount: Record<string, number> = {};
  let blueRangedMageMm = 0, redRangedMageMm = 0;
  let blueEngage = 0, redEngage = 0;

  for (const tag of ALL_TAGS) {
    blueTagsCount[tag] = 0;
    redTagsCount[tag] = 0;
  }

  for (let i = 0; i < POSITION_ORDER.length; i++) {
    const pos = POSITION_ORDER[i];
    const short = POSITION_SHORT[pos];
    const bId = blueByPos[pos]?.championId ?? 0;
    const rId = redByPos[pos]?.championId ?? 0;

    const bChamp = bId ? ddragon.getChampion(bId) : null;
    const rChamp = rId ? ddragon.getChampion(rId) : null;
    const bTags = bChamp?.tags ?? [];
    const rTags = rChamp?.tags ?? [];
    const bTagSet = new Set(bTags);
    const rTagSet = new Set(rTags);

    features[`${short}_tag_advantage`] = tagAdvantageScore(bTags, rTags);

    const bRange = bId ? ddragon.getAttackRange(bId) : 550;
    const rRange = rId ? ddragon.getAttackRange(rId) : 550;
    features[`${short}_range_diff`] = bRange - rRange;

    const bMelee = bId ? ddragon.isMelee(bId) : false;
    const rMelee = rId ? ddragon.isMelee(rId) : false;
    if (bMelee && !rMelee) features[`${short}_melee_vs_ranged`] = 1.0;
    else if (!bMelee && rMelee) features[`${short}_melee_vs_ranged`] = -1.0;
    else features[`${short}_melee_vs_ranged`] = 0.0;

    const bCf = blueChampFeats[i] ?? {};
    const rCf = redChampFeats[i] ?? {};

    if ((bCf.is_ap_champ ?? 0) > 0.5) blueAp++;
    else if ((bCf.is_mixed_champ ?? 0) < 0.5) blueAd++;
    if ((rCf.is_ap_champ ?? 0) > 0.5) redAp++;
    else if ((rCf.is_mixed_champ ?? 0) < 0.5) redAd++;

    blueArmorSum += bCf.champ_armor_base ?? 33.0;
    redArmorSum += rCf.champ_armor_base ?? 33.0;

    for (const tag of ALL_TAGS) {
      if (bTagSet.has(tag)) blueTagsCount[tag]++;
      if (rTagSet.has(tag)) redTagsCount[tag]++;
    }

    if ((bTagSet.has("Mage") || bTagSet.has("Marksman")) && !bMelee) blueRangedMageMm++;
    if ((rTagSet.has("Mage") || rTagSet.has("Marksman")) && !rMelee) redRangedMageMm++;

    if (bMelee && (bTagSet.has("Tank") || bTagSet.has("Fighter"))) blueEngage++;
    if (rMelee && (rTagSet.has("Tank") || rTagSet.has("Fighter"))) redEngage++;
  }

  features.team_ap_diff = blueAp - redAp;
  features.team_ad_diff = blueAd - redAd;

  const blueEntropy = shannonEntropy([blueAp, blueAd, Math.max(0, 5 - blueAp - blueAd)]);
  const redEntropy = shannonEntropy([redAp, redAd, Math.max(0, 5 - redAp - redAd)]);
  features.team_damage_diversity_diff = blueEntropy - redEntropy;

  features.team_armor_vs_ap =
    (blueArmorSum / 5.0) * redAp - (redArmorSum / 5.0) * blueAp;

  features.frontline_diff =
    (blueTagsCount.Tank + blueTagsCount.Fighter) -
    (redTagsCount.Tank + redTagsCount.Fighter);
  features.engage_diff = blueEngage - redEngage;
  features.backline_diff =
    (blueTagsCount.Mage + blueTagsCount.Marksman) -
    (redTagsCount.Mage + redTagsCount.Marksman);
  features.poke_diff = blueRangedMageMm - redRangedMageMm;
  features.peel_diff =
    (blueTagsCount.Support + blueTagsCount.Tank) -
    (redTagsCount.Support + redTagsCount.Tank);
  features.dive_diff =
    (blueTagsCount.Assassin + blueTagsCount.Fighter) -
    (redTagsCount.Assassin + redTagsCount.Fighter);

  return features;
}

function patchToNumeric(version: string): number {
  const parts = version.split(".");
  if (parts.length >= 2) {
    return parseInt(parts[0], 10) * 100 + parseInt(parts[1], 10);
  }
  return 0;
}

const LCU_POSITION_MAP: Record<string, string> = {
  top: "TOP",
  jungle: "JUNGLE",
  middle: "MIDDLE",
  bottom: "BOTTOM",
  utility: "UTILITY",
};

export function buildPregameFeatures(
  session: ChampSelectSession,
  rankedStats?: RankedStats | null,
  featureNames?: string[],
): Record<string, number> {
  const features: Record<string, number> = {};
  features.patch_numeric = patchToNumeric(ddragon.getChampionVersion());

  const localTeam = session.myTeam[0]?.team ?? 1;
  const isBlue = localTeam === 1;

  const bluePlayers = isBlue ? session.myTeam : session.theirTeam;
  const redPlayers = isBlue ? session.theirTeam : session.myTeam;

  const localCellId = session.localPlayerCellId;

  const soloQ = rankedStats?.queueMap?.RANKED_SOLO_5x5;
  const localRankOpts: PlayerFeatureOpts | undefined = soloQ
    ? {
        rankedTier: soloQ.tier,
        rankedDivision: soloQ.division,
        rankedLP: soloQ.leaguePoints,
        rankedWins: soloQ.wins,
        rankedLosses: soloQ.losses,
      }
    : undefined;

  const blueByPos: Record<string, { championId: number }> = {};
  const redByPos: Record<string, { championId: number }> = {};
  const bluePlayerFeatsByPos: Record<string, Record<string, number>> = {};
  const redPlayerFeatsByPos: Record<string, Record<string, number>> = {};
  const bluePlayerFeatsList: Record<string, number>[] = [];
  const redPlayerFeatsList: Record<string, number>[] = [];
  const blueChampFeatsList: Record<string, number>[] = [];
  const redChampFeatsList: Record<string, number>[] = [];

  for (const [side, players, byPos, pfByPos, pfList, cfList] of [
    ["blue", bluePlayers, blueByPos, bluePlayerFeatsByPos, bluePlayerFeatsList, blueChampFeatsList],
    ["red", redPlayers, redByPos, redPlayerFeatsByPos, redPlayerFeatsList, redChampFeatsList],
  ] as const) {
    const positionedPlayers = alignPlayersToPositions(players);

    for (const pos of POSITION_ORDER) {
      const short = POSITION_SHORT[pos];
      const player = positionedPlayers[pos];
      const champId = player?.championId ?? 0;

      (byPos as Record<string, { championId: number }>)[pos] = { championId: champId };

      const isLocal = player != null && allTeamPlayers(session).some(
        (p) => p === player || (p.summonerId === player.summonerId && p.summonerId !== 0),
      ) && isPlayerLocal(player, localCellId, session);

      let pf: Record<string, number>;
      if (isLocal && localRankOpts) {
        pf = extractPlayerFeatures({
          ...localRankOpts,
          spell1Id: player?.spell1Id,
          spell2Id: player?.spell2Id,
        });
      } else if (player && (player.spell1Id || player.spell2Id)) {
        pf = extractPlayerFeatures({
          spell1Id: player.spell1Id,
          spell2Id: player.spell2Id,
        });
      } else {
        pf = extractPlayerFeatures();
      }

      const cf = champId > 0 ? extractChampionFeatures(champId) : extractChampionFeatures(0);

      (pfByPos as Record<string, Record<string, number>>)[pos] = pf;
      (pfList as Record<string, number>[]).push(pf);
      (cfList as Record<string, number>[]).push(cf);

      for (const [k, v] of Object.entries(pf)) {
        features[`${side}_${short}_${k}`] = v;
      }
      for (const [k, v] of Object.entries(cf)) {
        features[`${side}_${short}_${k}`] = v;
      }
    }
  }

  const blueTeam = extractTeamFeatures(bluePlayerFeatsList, blueChampFeatsList);
  const redTeam = extractTeamFeatures(redPlayerFeatsList, redChampFeatsList);
  for (const [k, v] of Object.entries(blueTeam)) features[`blue_${k}`] = v;
  for (const [k, v] of Object.entries(redTeam)) features[`red_${k}`] = v;

  const draft = extractDraftFeatures(bluePlayerFeatsByPos, redPlayerFeatsByPos);
  Object.assign(features, draft);

  const interaction = extractInteractionFeatures(
    blueByPos, redByPos, blueChampFeatsList, redChampFeatsList,
  );
  Object.assign(features, interaction);

  const blueBanCount = session.bans?.myTeamBans?.filter((b) => b > 0).length ?? 0;
  const redBanCount = session.bans?.theirTeamBans?.filter((b) => b > 0).length ?? 0;
  if (isBlue) {
    features.blue_bans_count = blueBanCount;
    features.red_bans_count = redBanCount;
  } else {
    features.blue_bans_count = redBanCount;
    features.red_bans_count = blueBanCount;
  }
  features.blue_target_banned = 0;
  features.red_target_banned = 0;

  if (featureNames) {
    const result: Record<string, number> = {};
    for (const name of featureNames) {
      result[name] = features[name] ?? 0.0;
    }
    return result;
  }

  return features;
}

function alignPlayersToPositions(
  players: ChampSelectSession["myTeam"],
): Record<string, ChampSelectSession["myTeam"][number]> {
  const byPos: Record<string, ChampSelectSession["myTeam"][number]> = {};
  for (const p of players) {
    const pos = LCU_POSITION_MAP[p.assignedPosition?.toLowerCase()] ?? p.assignedPosition?.toUpperCase();
    if (pos && POSITION_ORDER.includes(pos as typeof POSITION_ORDER[number])) {
      byPos[pos] = p;
    }
  }
  return byPos;
}

function allTeamPlayers(session: ChampSelectSession) {
  return [...session.myTeam, ...session.theirTeam];
}

function isPlayerLocal(
  player: ChampSelectSession["myTeam"][number],
  localCellId: number,
  session: ChampSelectSession,
): boolean {
  const allPlayers = allTeamPlayers(session);
  const idx = allPlayers.indexOf(player);
  return idx === localCellId;
}

export function getPregameSummaryFromFeatures(
  features: Record<string, number>,
): Record<string, number> {
  return {
    melee_count_diff: (features.blue_melee_count ?? 0) - (features.red_melee_count ?? 0),
    ad_ratio_diff: (features.blue_ad_ratio ?? 0) - (features.red_ad_ratio ?? 0),
    scaling_score_diff: 0,
    avg_rank_diff: (features.blue_avg_rank ?? 12) - (features.red_avg_rank ?? 12),
    avg_winrate_diff: (features.blue_avg_team_winrate ?? 0.5) - (features.red_avg_team_winrate ?? 0.5),
  };
}
