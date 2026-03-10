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

export interface CurrentSummoner {
  puuid: string;
  gameName: string;
  tagLine: string;
  summonerId: number;
  displayName: string;
}

export interface GameflowPlayer {
  championId: number;
  selectedPosition: string;
  summonerId: number;
  spell1Id: number;
  spell2Id: number;
  team: number;
}

export interface GameflowSession {
  gameData: {
    teamOne: GameflowPlayer[];
    teamTwo: GameflowPlayer[];
  };
}

export interface LCUMatchHistoryResponse {
  games: {
    games: LCUGame[];
  };
}

export interface LCUGame {
  gameId: number;
  gameCreation: number;
  gameDuration: number;
  queueId: number;
  participants: LCUParticipant[];
  participantIdentities: LCUParticipantIdentity[];
}

export interface LCUParticipant {
  participantId: number;
  championId: number;
  teamId: number;
  spell1Id: number;
  spell2Id: number;
  stats: {
    win: boolean;
    kills: number;
    deaths: number;
    assists: number;
    totalMinionsKilled: number;
    neutralMinionsKilled: number;
    goldEarned: number;
    totalDamageDealtToChampions: number;
    visionScore: number;
    champLevel: number;
    totalDamageTaken: number;
    item0: number;
    item1: number;
    item2: number;
    item3: number;
    item4: number;
    item5: number;
    item6: number;
  };
  timeline?: {
    role: string;
    lane: string;
  };
}

export interface LCUParticipantIdentity {
  participantId: number;
  player: {
    puuid: string;
    gameName: string;
    tagLine: string;
    summonerId: number;
    championId?: number;
  };
}
