import { RefreshCw, WifiOff, Loader2 } from "lucide-react";
import { usePlayerInfo } from "../hooks/usePlayerInfo";
import Card from "./Card";
import MatchCard from "./MatchCard";
import RankCard from "./RankCard";
import ChampionStatsGrid from "./ChampionStatsGrid";

export default function PlayerInfo() {
  const {
    identity,
    matches,
    totalMatches,
    championStats,
    rankedStats,
    loading,
    lcuConnected,
    loadMore,
    filterByChampion,
    championFilter,
    refresh,
  } = usePlayerInfo();

  if (!identity) {
    return (
      <Card>
        <div className="waiting-state">
          <div className="waiting-state__title">No Player Data</div>
          <div className="waiting-state__subtitle">
            Open the League Client to load your profile
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="player-info">
      <div className="player-info__header">
        <div className="player-info__identity">
          <span className="player-info__name">{identity.gameName}</span>
          <span className="player-info__tag">#{identity.tagLine}</span>
        </div>
        <div className="player-info__actions">
          {!lcuConnected && (
            <div className="player-info__offline">
              <WifiOff size={12} />
              <span>Offline — cached data</span>
            </div>
          )}
          <button className="icon-btn" onClick={refresh} title="Refresh data">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      <RankCard stats={rankedStats} />

      <ChampionStatsGrid
        stats={championStats}
        onChampionClick={filterByChampion}
        activeChampion={championFilter}
      />

      <div className="player-info__matches">
        <h3 className="section-title">Match History</h3>
        {matches.length === 0 && !loading && (
          <div className="player-info__empty">
            No matches found{championFilter ? " for this champion" : ""}
          </div>
        )}
        {matches.map((m) => (
          <MatchCard key={m.match_id} match={m} />
        ))}
        {loading && (
          <div className="player-info__loading">
            <Loader2 size={16} className="spin" />
            Loading...
          </div>
        )}
        {!loading && matches.length < totalMatches && (
          <button className="player-info__load-more" onClick={loadMore}>
            Load more ({totalMatches - matches.length} remaining)
          </button>
        )}
      </div>
    </div>
  );
}
