import type { RankedStatsRow } from "../types";
import { winRateColor } from "../utils";

const QUEUE_LABELS: Record<string, string> = {
  RANKED_SOLO_5x5: "Solo/Duo",
  RANKED_FLEX_SR: "Flex",
  RANKED_TFT: "TFT",
  RANKED_TFT_TURBO: "TFT Hyper Roll",
};

const TIER_COLORS: Record<string, string> = {
  IRON: "#6b6b6b",
  BRONZE: "#a0714e",
  SILVER: "#8a9bae",
  GOLD: "#c8aa6e",
  PLATINUM: "#4e9e8e",
  EMERALD: "#2dce89",
  DIAMOND: "#576cce",
  MASTER: "#9d4dbb",
  GRANDMASTER: "#e84057",
  CHALLENGER: "#f0d78c",
};

export default function RankCard({ stats }: { stats: RankedStatsRow[] }) {
  const soloQueue = stats.find((s) => s.queue_type === "RANKED_SOLO_5x5");
  const flexQueue = stats.find((s) => s.queue_type === "RANKED_FLEX_SR");

  const queues = [soloQueue, flexQueue].filter((q): q is RankedStatsRow => q != null && q.tier != null);

  if (queues.length === 0) return null;

  return (
    <div className="rank-card">
      {queues.map((q) => {
        const wins = q.wins ?? 0;
        const losses = q.losses ?? 0;
        const total = wins + losses;
        const wr = total > 0 ? Math.round((wins / total) * 100) : 0;
        const tierColor = TIER_COLORS[q.tier?.toUpperCase() ?? ""] ?? "var(--text-secondary)";
        const tierDisplay = q.tier ? q.tier.charAt(0) + q.tier.slice(1).toLowerCase() : "";
        const divDisplay = q.division && q.division !== "NA" ? ` ${q.division}` : "";

        return (
          <div key={q.queue_type} className="rank-card__queue">
            <div className="rank-card__label">
              {QUEUE_LABELS[q.queue_type] ?? q.queue_type}
            </div>
            <div className="rank-card__tier" style={{ color: tierColor }}>
              {tierDisplay}{divDisplay}
            </div>
            <div className="rank-card__lp">{q.lp} LP</div>
            <div className="rank-card__record">
              <span className="rank-card__wins">{wins}W</span>
              <span className="rank-card__losses">{losses}L</span>
              <span className="rank-card__winrate" style={{ color: winRateColor(wr) }}>
                {wr}%
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
