import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Search, Loader2, UserX } from "lucide-react";
import Card from "../components/Card";
import { lookupPlayer, predictLiveGame } from "../api";
import { tooltipStyle, sectionTitle, primaryButton } from "../styles";
import type { PredictLookup, PredictResult, PredictParticipant } from "../types";

type Stage = "idle" | "searching" | "not_in_game" | "predicting" | "result" | "error";

const POSITION_LABELS: Record<string, string> = {
  TOP: "Top",
  JUNGLE: "Jungle",
  MIDDLE: "Mid",
  BOTTOM: "Bot",
  UTILITY: "Support",
  UNKNOWN: "?",
};

const TIER_COLORS: Record<string, string> = {
  IRON: "#5c5c5c",
  BRONZE: "#a0522d",
  SILVER: "#8a9ba8",
  GOLD: "#f0b232",
  PLATINUM: "#1ad4a8",
  EMERALD: "#0acf83",
  DIAMOND: "#6898f0",
  MASTER: "#9a60e4",
  GRANDMASTER: "#ef4444",
  CHALLENGER: "#f0b232",
};

function formatRank(rank: PredictParticipant["rank"]): string {
  if (!rank) return "Unranked";
  return `${rank.tier[0]}${rank.tier.slice(1).toLowerCase()} ${rank.rank}`;
}

function formatFeatureName(name: string): string {
  return name
    .replace(/^(blue|red)_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function LivePredict() {
  const [riotId, setRiotId] = useState("");
  const [stage, setStage] = useState<Stage>("idle");
  const [lookup, setLookup] = useState<PredictLookup | null>(null);
  const [prediction, setPrediction] = useState<PredictResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch() {
    const hash = riotId.indexOf("#");
    if (hash === -1 || hash === 0 || hash === riotId.length - 1) {
      setError("Enter Riot ID as Name#TAG");
      setStage("error");
      return;
    }
    const gameName = riotId.slice(0, hash);
    const tagLine = riotId.slice(hash + 1);

    setStage("searching");
    setError(null);
    setPrediction(null);

    try {
      const result = await lookupPlayer(gameName, tagLine);
      setLookup(result);

      if (!result.found) {
        setError(result.error || "Player not found");
        setStage("error");
        return;
      }

      if (!result.in_game) {
        setStage("not_in_game");
        return;
      }

      setStage("predicting");
      const pred = await predictLiveGame(result.game_data);
      setPrediction(pred);
      setStage("result");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setStage("error");
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSearch();
  }

  const blue = prediction?.participants.filter((p) => p.team_id === 100) ?? [];
  const red = prediction?.participants.filter((p) => p.team_id === 200) ?? [];
  const blueBans = prediction?.bans.filter((b) => b.team_id === 100) ?? [];
  const redBans = prediction?.bans.filter((b) => b.team_id === 200) ?? [];

  const factorData = prediction?.top_factors
    .slice(0, 10)
    .reverse()
    .map((f) => ({
      name: formatFeatureName(f.feature),
      impact: parseFloat(f.impact.toFixed(4)),
      fill: f.impact > 0 ? "var(--blue)" : "var(--red)",
    })) ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 900, margin: "0 auto" }}>
      <Card>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <input
            type="text"
            value={riotId}
            onChange={(e) => setRiotId(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Riot ID (e.g. Doublelift#NA1)"
            style={styles.input}
          />
          <button
            onClick={handleSearch}
            disabled={stage === "searching" || stage === "predicting"}
            style={{
              ...primaryButton,
              opacity: stage === "searching" || stage === "predicting" ? 0.5 : 1,
            }}
          >
            {stage === "searching" || stage === "predicting" ? (
              <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
            ) : (
              <Search size={16} />
            )}
            {stage === "searching" ? "Looking up..." : stage === "predicting" ? "Predicting..." : "Search"}
          </button>
        </div>
      </Card>

      {stage === "error" && error && (
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--red)" }}>
            <UserX size={18} />
            <span style={{ fontSize: 14 }}>{error}</span>
          </div>
        </Card>
      )}

      {stage === "not_in_game" && lookup && (
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--text-secondary)" }}>
            <UserX size={18} />
            <span style={{ fontSize: 14 }}>
              <span className="mono" style={{ color: "var(--text-primary)", fontWeight: 600 }}>
                {lookup.game_name}#{lookup.tag_line}
              </span>
              {" "}is not currently in a game.
            </span>
          </div>
        </Card>
      )}

      {stage === "predicting" && (
        <Card glow>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Loader2 size={18} style={{ color: "var(--accent)", animation: "spin 1s linear infinite" }} />
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Analyzing live game...</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                Enriching player data and running prediction model
              </div>
            </div>
          </div>
        </Card>
      )}

      {stage === "result" && prediction && (
        <>
          <Card>
            <ProbabilityBar probability={prediction.blue_win_probability} />
          </Card>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <TeamCard
              label="BLUE SIDE"
              color="var(--blue)"
              players={blue}
              bans={blueBans}
            />
            <TeamCard
              label="RED SIDE"
              color="var(--red)"
              players={red}
              bans={redBans}
            />
          </div>

          {factorData.length > 0 && (
            <Card>
              <h3 style={sectionTitle}>Top Prediction Factors</h3>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4, marginBottom: 12 }}>
                <span style={{ color: "var(--blue)" }}>Blue</span> = favors blue side
                {" / "}
                <span style={{ color: "var(--red)" }}>Red</span> = favors red side
              </div>
              <div style={{ height: 320 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={factorData}
                    layout="vertical"
                    margin={{ top: 5, right: 20, bottom: 5, left: 140 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis type="number" tick={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                      width={135}
                    />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="impact" radius={[4, 4, 4, 4]}>
                      {factorData.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function ProbabilityBar({ probability }: { probability: number }) {
  const bluePct = (probability * 100).toFixed(1);
  const redPct = ((1 - probability) * 100).toFixed(1);
  const favored = probability >= 0.5 ? "BLUE" : "RED";
  const confidence = Math.abs(probability - 0.5) * 200;

  return (
    <div>
      <div style={{ textAlign: "center", marginBottom: 16 }}>
        <span
          className="mono"
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: favored === "BLUE" ? "var(--blue)" : "var(--red)",
            textTransform: "uppercase",
            letterSpacing: "1px",
          }}
        >
          {favored} FAVORED
        </span>
        {confidence > 5 && (
          <span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 8 }}>
            ({confidence.toFixed(0)}% edge)
          </span>
        )}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <span className="mono" style={{ fontSize: 32, fontWeight: 700, color: "var(--blue)" }}>
          {bluePct}%
        </span>
        <span className="mono" style={{ fontSize: 32, fontWeight: 700, color: "var(--red)" }}>
          {redPct}%
        </span>
      </div>

      <div style={{ display: "flex", height: 14, borderRadius: 7, overflow: "hidden", background: "var(--bg-primary)" }}>
        <div
          style={{
            width: `${bluePct}%`,
            background: "var(--blue)",
            transition: "width 0.6s ease",
            borderRadius: "7px 0 0 7px",
          }}
        />
        <div
          style={{
            width: `${redPct}%`,
            background: "var(--red)",
            transition: "width 0.6s ease",
            borderRadius: "0 7px 7px 0",
          }}
        />
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
        <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
          Blue Side
        </span>
        <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
          Red Side
        </span>
      </div>
    </div>
  );
}

function TeamCard({
  label,
  color,
  players,
  bans,
}: {
  label: string;
  color: string;
  players: PredictParticipant[];
  bans: { champion_id: number; champion_name: string; team_id: number }[];
}) {
  return (
    <Card>
      <h3 style={{ ...sectionTitle, color, marginBottom: 12 }}>{label}</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {players.map((p) => (
          <div key={p.puuid} style={styles.playerRow}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
              <span style={styles.posTag}>{POSITION_LABELS[p.position] ?? p.position}</span>
              <span style={{ fontSize: 13, fontWeight: 500 }}>{p.champion_name}</span>
            </div>
            <span
              className="mono"
              style={{
                fontSize: 11,
                color: TIER_COLORS[p.rank?.tier ?? ""] ?? "var(--text-muted)",
                fontWeight: 500,
              }}
            >
              {formatRank(p.rank)}
            </span>
          </div>
        ))}
      </div>
      {bans.length > 0 && (
        <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
          <span style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "1px" }}>
            Bans
          </span>
          <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
            {bans.map((b, i) => (
              <span key={i} style={styles.banChip}>
                {b.champion_name}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

const styles: Record<string, React.CSSProperties> = {
  input: {
    flex: 1,
    padding: "10px 14px",
    fontSize: 14,
    fontFamily: "'JetBrains Mono', monospace",
    color: "var(--text-primary)",
    background: "var(--bg-input)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    outline: "none",
  },
  playerRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "6px 10px",
    background: "var(--bg-primary)",
    borderRadius: 6,
  },
  posTag: {
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.5px",
    color: "var(--text-muted)",
    width: 50,
    flexShrink: 0,
  },
  banChip: {
    fontSize: 11,
    padding: "2px 8px",
    background: "var(--bg-primary)",
    border: "1px solid var(--border)",
    borderRadius: 4,
    color: "var(--text-secondary)",
  },
};
