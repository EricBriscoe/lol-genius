export interface LCUCredentials {
  port: number;
  password: string;
  pid: number;
}

export interface ChampSelectPlayer {
  summonerId: number;
  championId: number;
  assignedPosition: string;
  spell1Id: number;
  spell2Id: number;
  team: number;
}

export interface ChampSelectSession {
  myTeam: ChampSelectPlayer[];
  theirTeam: ChampSelectPlayer[];
  bans: { myTeamBans: number[]; theirTeamBans: number[] };
  timer: { phase: string; adjustedTimeLeftInPhase: number };
  localPlayerCellId: number;
}

export interface RankedStats {
  queueMap: Record<string, {
    tier: string;
    division: string;
    leaguePoints: number;
    wins: number;
    losses: number;
    isProvisional: boolean;
  }>;
}
