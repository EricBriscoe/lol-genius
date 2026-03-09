import type { PredictFactor } from "../types";
import { titleCase } from "../utils";

const LABELS: Record<string, string> = {
  kill_diff: "Kill Lead",
  tower_diff: "Tower Lead",
  dragon_diff: "Dragon Lead",
  cs_diff: "CS Lead",
  inhibitor_diff: "Inhibitor Lead",
  elder_diff: "Elder Lead",
  pregame_blue_win_prob: "Pregame Prediction",
  game_time_seconds: "Game Time",
  avg_rank_diff: "Avg Rank",
  avg_winrate_diff: "Winrate Adv.",
  avg_mastery_diff: "Mastery Adv.",
  avg_champ_wr_diff: "Champ WR Adv.",
};

function featureLabel(name: string): string {
  return LABELS[name] ?? titleCase(name);
}

export default function KeyFactors({ factors }: { factors: PredictFactor[] }) {
  const maxImpact = Math.max(...factors.map((f) => Math.abs(f.impact)), 0.001);
  return (
    <div className="key-factors">
      {factors.map((f) => {
        const label = featureLabel(f.feature);
        const pct = (Math.abs(f.impact) / maxImpact) * 100;
        const positive = f.impact >= 0;
        return (
          <div key={f.feature} className="key-factors__row">
            <div className="key-factors__label">{label}</div>
            <div className="key-factors__bar-track">
              <div
                className={`key-factors__bar-fill key-factors__bar-fill--${positive ? "positive" : "negative"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="key-factors__impact" style={{ color: positive ? "var(--accent)" : "var(--red)" }}>
              {positive ? "+" : ""}{f.impact.toFixed(3)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
