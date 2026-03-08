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
    <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 12 }}>
      {factors.map((f) => {
        const label = featureLabel(f.feature);
        const pct = (Math.abs(f.impact) / maxImpact) * 100;
        const positive = f.impact >= 0;
        return (
          <div key={f.feature} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 140, textAlign: "right", fontSize: 12, color: "var(--text-secondary)", flexShrink: 0 }}>
              {label}
            </div>
            <div style={{ flex: 1, height: 12, background: "var(--bg-primary)", borderRadius: 4, overflow: "hidden" }}>
              <div style={{
                width: `${pct}%`,
                height: "100%",
                background: positive ? "var(--accent)" : "var(--red)",
                borderRadius: 4,
                transition: "width 0.4s ease",
              }} />
            </div>
            <div className="mono" style={{ width: 52, fontSize: 11, color: positive ? "var(--accent)" : "var(--red)", textAlign: "right", flexShrink: 0 }}>
              {positive ? "+" : ""}{f.impact.toFixed(3)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
