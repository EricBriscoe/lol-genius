import type { FactorAnalysis } from "../types";

export default function KeyFactors({ analysis }: { analysis: FactorAnalysis }) {
  const { groups, narrative } = analysis;
  if (groups.length === 0) return null;

  const maxPct = Math.max(...groups.map((g) => Math.abs(g.impactPct)), 1);

  return (
    <div className="key-factors">
      {narrative && <div className="key-factors__narrative">{narrative}</div>}
      {groups.map((g) => {
        const pct = (Math.abs(g.impactPct) / maxPct) * 45;
        const positive = g.impactPct >= 0;
        return (
          <div key={g.category} className="key-factors__row">
            <div className="key-factors__label">{g.category}</div>
            <div className="key-factors__bar-track">
              <div className="key-factors__center-line" />
              <div
                className={`key-factors__bar-fill key-factors__bar-fill--${positive ? "blue" : "red"}`}
                style={{
                  width: `${pct}%`,
                  ...(positive
                    ? { left: "50%" }
                    : { right: "50%" }),
                }}
              />
            </div>
            <div
              className="key-factors__impact"
              style={{ color: positive ? "var(--accent)" : "var(--red)" }}
            >
              {positive ? "+" : ""}{g.impactPct.toFixed(1)}%
            </div>
          </div>
        );
      })}
    </div>
  );
}
