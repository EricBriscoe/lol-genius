export interface PlayerIdentity {
  puuid: string;
  gameName: string;
  tagLine: string;
  summonerId: string;
}

export interface MatchRow {
  match_id: string;
  puuid: string;
  game_creation: number;
  game_duration: number | null;
  queue_id: number | null;
  champion_id: number | null;
  champion_name: string | null;
  team_position: string | null;
  win: number | null;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  cs: number | null;
  gold_earned: number | null;
  total_damage: number | null;
  vision_score: number | null;
  champion_level: number | null;
  total_damage_taken: number | null;
  item0: number | null;
  item1: number | null;
  item2: number | null;
  item3: number | null;
  item4: number | null;
  item5: number | null;
  item6: number | null;
  summoner_spell1: number | null;
  summoner_spell2: number | null;
  participants_json: string | null;
}

export interface RankedStatsRow {
  puuid: string;
  queue_type: string;
  tier: string | null;
  division: string | null;
  lp: number | null;
  wins: number | null;
  losses: number | null;
  updated_at: number;
}

export interface ChampionStatsAgg {
  champion_id: number;
  champion_name: string;
  games: number;
  wins: number;
  avg_kills: number;
  avg_deaths: number;
  avg_assists: number;
  avg_cs: number;
}

export interface MatchHistoryResult {
  matches: MatchRow[];
  total: number;
  source: "cache" | "lcu";
  lcuOffline?: boolean;
}

export interface MatchHistoryParams {
  offset: number;
  limit: number;
  championId?: number;
  queueId?: number;
}
