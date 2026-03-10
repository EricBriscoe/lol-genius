import type { ChampionStatsAgg } from "../types";
import { champIconUrl, winRateColor, hideOnImgError } from "../utils";

export default function ChampionStatsGrid({ stats, onChampionClick, activeChampion }: {
  stats: ChampionStatsAgg[];
  onChampionClick: (id: number | undefined) => void;
  activeChampion?: number;
}) {
  if (stats.length === 0) return null;

  const top = stats.slice(0, 10);

  return (
    <div className="champ-stats">
      <div className="champ-stats__header">
        <h3 className="section-title">Champions</h3>
        {activeChampion != null && (
          <button className="btn-clear champ-stats__clear" onClick={() => onChampionClick(undefined)}>
            Clear filter
          </button>
        )}
      </div>
      <div className="champ-stats__grid">
        {top.map((c) => {
          const wr = c.games > 0 ? Math.round((c.wins / c.games) * 100) : 0;
          const isActive = activeChampion === c.champion_id;
          const kda = c.avg_deaths > 0
            ? ((c.avg_kills + c.avg_assists) / c.avg_deaths).toFixed(2)
            : "Perfect";

          return (
            <div
              key={c.champion_id}
              className={`champ-stats__row ${isActive ? "champ-stats__row--active" : ""}`}
              onClick={() => onChampionClick(isActive ? undefined : c.champion_id)}
            >
              <img
                className="champ-stats__icon"
                src={champIconUrl(c.champion_id)}
                alt=""
                onError={hideOnImgError}
              />
              <div className="champ-stats__info">
                <span className="champ-stats__name">{c.champion_name || `Champ ${c.champion_id}`}</span>
                <span className="champ-stats__games">{c.games} games</span>
              </div>
              <div className="champ-stats__winrate" style={{ color: winRateColor(wr) }}>
                {wr}%
              </div>
              <div className="champ-stats__kda">{kda} KDA</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
