import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Wifi, WifiOff, Play, Square, AlertTriangle } from "lucide-react";
import Card from "../components/Card";
import { startLiveGame, stopLiveGame, fetchLiveGameStatus } from "../api";
import { sectionTitle } from "../styles";
import type { LiveGameUpdate, LiveGameStatus, PredictFactor } from "../types";
import { formatFeatureName } from "../utils";

interface Props {
  latestUpdate: LiveGameUpdate | null;
}

function fmtTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function diffColor(diff: number): string | undefined {
  return diff > 0 ? "var(--accent)" : diff < 0 ? "var(--red)" : undefined;
}

function StatBox({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{
      background: "var(--bg-primary)",
      border: "1px solid var(--border)",
      borderRadius: 8,
      padding: "12px 16px",
      textAlign: "center",
    }}>
      <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4 }}>{label}</div>
      <div className="mono" style={{ fontSize: 22, fontWeight: 700, color: color || "var(--text-primary)" }}>{value}</div>
    </div>
  );
}

const FEATURE_LABEL_OVERRIDES: Record<string, string> = {
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
  return FEATURE_LABEL_OVERRIDES[name] ?? formatFeatureName(name);
}

function KeyFactors({ factors }: { factors: PredictFactor[] }) {
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

const RECENTS_KEY = "lol_genius_live_recents";
const MAX_RECENTS = 5;

function loadRecents(): { host: string; port: string }[] {
  try {
    return JSON.parse(localStorage.getItem(RECENTS_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveRecent(host: string, port: string): { host: string; port: string }[] {
  const updated = [
    { host, port },
    ...loadRecents().filter((r) => !(r.host === host && r.port === port)),
  ].slice(0, MAX_RECENTS);
  localStorage.setItem(RECENTS_KEY, JSON.stringify(updated));
  return updated;
}

export default function LiveGame({ latestUpdate }: Props) {
  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState("2999");
  const [connected, setConnected] = useState(false);
  const [pollerStatus, setPollerStatus] = useState<string>("waiting");
  const [history, setHistory] = useState<{ game_time: number; probability: number }[]>([]);
  const [current, setCurrent] = useState<LiveGameUpdate | null>(null);
  const [recents, setRecents] = useState<{ host: string; port: string }[]>(loadRecents);

  useEffect(() => {
    fetchLiveGameStatus().then((s: LiveGameStatus) => {
      setConnected(s.connected);
      if (s.host) setHost(s.host);
      if (s.port) setPort(String(s.port));
      if (s.status) setPollerStatus(s.status);
      setHistory(s.history);
      setCurrent(s.current);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!latestUpdate) return;
    const { status, blue_win_probability, game_reset } = latestUpdate;
    if (status === "model_missing" || status === "poll_error" || status === "no_data") {
      setPollerStatus(status);
      return;
    }
    if (blue_win_probability == null) return;
    setPollerStatus("ok");
    setCurrent(latestUpdate);
    setHistory((prev) => {
      const base = game_reset ? [] : prev;
      const entry = { game_time: latestUpdate.game_time, probability: Math.round(blue_win_probability * 100 * 10) / 10 };
      if (base.length > 0 && base[base.length - 1].game_time === entry.game_time) return base;
      const next = [...base, entry];
      return next.length > 100 ? next.slice(-100) : next;
    });
  }, [latestUpdate]);

  async function handleConnect() {
    const portNum = Number(port);
    if (isNaN(portNum) || portNum < 1 || portNum > 65535) return;
    try {
      await startLiveGame(host, portNum);
      setConnected(true);
      setPollerStatus("waiting");
      setHistory([]);
      setCurrent(null);
      setRecents(saveRecent(host, port));
    } catch {}
  }

  async function handleDisconnect() {
    try {
      await stopLiveGame();
      setConnected(false);
    } catch {}
  }

  const blueProb = current && current.blue_win_probability != null ? Math.round(current.blue_win_probability * 100) : 50;
  const redProb = 100 - blueProb;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Card>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 12 }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>Host</label>
            <input
              value={host}
              onChange={(e) => setHost(e.target.value)}
              disabled={connected}
              style={inputStyle}
            />
          </div>
          <div style={{ width: 100 }}>
            <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>Port</label>
            <input
              value={port}
              onChange={(e) => setPort(e.target.value)}
              disabled={connected}
              style={inputStyle}
            />
          </div>
          {connected ? (
            <button onClick={handleDisconnect} style={disconnectBtn}>
              <Square size={14} /> Disconnect
            </button>
          ) : (
            <button onClick={handleConnect} style={connectBtn}>
              <Play size={14} /> Connect
            </button>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6, paddingBottom: 8 }}>
            {connected ? (
              <Wifi size={16} style={{ color: "var(--accent)" }} />
            ) : (
              <WifiOff size={16} style={{ color: "var(--text-muted)" }} />
            )}
            <span style={{ fontSize: 12, color: connected ? "var(--accent)" : "var(--text-muted)" }}>
              {connected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>
        {!connected && recents.length > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, color: "var(--text-muted)", whiteSpace: "nowrap" }}>Recent:</span>
            {recents.map((r) => (
              <button
                key={`${r.host}:${r.port}`}
                onClick={() => { setHost(r.host); setPort(r.port); }}
                style={recentBtn}
              >
                {r.host}:{r.port}
              </button>
            ))}
          </div>
        )}
        {!connected && (
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 10 }}>
            Connect to the Riot Live Client Data API (LoL must be running). Polls every 15s and predicts with the live model.
          </p>
        )}
      </Card>

      {current && current.blue_win_probability != null && (
        <>
          <Card>
            <h3 style={sectionTitle}>Win Probability</h3>
            <div style={{ margin: "16px 0 8px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13, fontWeight: 600 }}>
                <span style={{ color: "var(--accent)" }}>Blue {blueProb}%</span>
                <span style={{ color: "var(--red)" }}>Red {redProb}%</span>
              </div>
              <div style={{ height: 28, borderRadius: 8, overflow: "hidden", display: "flex" }}>
                <div style={{
                  width: `${blueProb}%`,
                  background: "var(--accent)",
                  transition: "width 0.5s ease",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "flex-end",
                  paddingRight: 8,
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--bg-primary)",
                }}>
                  {blueProb > 20 && `${blueProb}%`}
                </div>
                <div style={{
                  flex: 1,
                  background: "var(--red)",
                  display: "flex",
                  alignItems: "center",
                  paddingLeft: 8,
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--bg-primary)",
                }}>
                  {redProb > 20 && `${redProb}%`}
                </div>
              </div>
            </div>
          </Card>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
            <StatBox label="Game Time" value={fmtTime(current.game_time)} />
            <StatBox label="Kill Diff" value={current.kill_diff >= 0 ? `+${current.kill_diff}` : current.kill_diff} color={diffColor(current.kill_diff)} />
            <StatBox label="CS Diff" value={current.cs_diff >= 0 ? `+${current.cs_diff}` : current.cs_diff} color={diffColor(current.cs_diff)} />
            <StatBox label="Tower Diff" value={current.tower_diff >= 0 ? `+${current.tower_diff}` : current.tower_diff} color={diffColor(current.tower_diff)} />
            <StatBox label="Baron Diff" value={current.baron_diff >= 0 ? `+${current.baron_diff}` : current.baron_diff} color={diffColor(current.baron_diff)} />
            <StatBox label="Dragon Diff" value={current.dragon_diff >= 0 ? `+${current.dragon_diff}` : current.dragon_diff} color={diffColor(current.dragon_diff)} />
            <StatBox label="Inhibitor Diff" value={current.inhibitor_diff >= 0 ? `+${current.inhibitor_diff}` : current.inhibitor_diff} color={diffColor(current.inhibitor_diff)} />
            <StatBox label="Elder Diff" value={current.elder_diff >= 0 ? `+${current.elder_diff}` : current.elder_diff} color={diffColor(current.elder_diff)} />
          </div>
        </>
      )}

      {current?.top_factors && current.top_factors.length > 0 && (
        <Card>
          <h3 style={sectionTitle}>Key Factors</h3>
          <KeyFactors factors={current.top_factors} />
        </Card>
      )}

      {history.length > 1 && (
        <Card>
          <h3 style={sectionTitle}>Win Probability History</h3>
          <div style={{ height: 240, marginTop: 12 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="game_time"
                  tickFormatter={(v) => fmtTime(v)}
                  tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                  label={{ value: "Game Time", position: "insideBottom", offset: -2, fill: "var(--text-muted)", fontSize: 11 }}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  contentStyle={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 12 }}
                  formatter={(v) => [`${v ?? 0}%`, "Blue Win %"]}
                  labelFormatter={(v) => `Time: ${fmtTime(v)}`}
                />
                <ReferenceLine y={50} stroke="var(--text-muted)" strokeDasharray="4 4" />
                <Line
                  type="monotone"
                  dataKey="probability"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  dot={{ fill: "var(--accent)", r: 3 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      {connected && !current && pollerStatus === "model_missing" && (
        <Card style={{ borderColor: "var(--red)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", color: "var(--red)", fontSize: 13 }}>
            <AlertTriangle size={16} />
            Live model not trained — run <code style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>lol-genius train --live</code> first
          </div>
        </Card>
      )}

      {connected && pollerStatus === "poll_error" && (
        <Card style={{ borderColor: "var(--gold)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", color: "var(--gold)", fontSize: 13 }}>
            <AlertTriangle size={16} />
            Poll error — check that the Live Client API is reachable
          </div>
        </Card>
      )}

      {connected && pollerStatus === "no_data" && (
        <Card style={{ borderColor: "var(--gold)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", color: "var(--gold)", fontSize: 13 }}>
            <AlertTriangle size={16} />
            No game detected at {host}:{port} — ensure League is running and in-game
          </div>
        </Card>
      )}

      {connected && !current && pollerStatus === "waiting" && (
        <Card>
          <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)", fontSize: 13 }}>
            Waiting for game data... (polls every 15 seconds)
          </div>
        </Card>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 12px",
  fontSize: 13,
  background: "var(--bg-input)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  color: "var(--text-primary)",
  outline: "none",
  fontFamily: "inherit",
};

const connectBtn: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  padding: "8px 16px",
  fontSize: 13,
  fontWeight: 600,
  fontFamily: "inherit",
  background: "var(--accent)",
  color: "var(--bg-primary)",
  border: "none",
  borderRadius: 6,
  cursor: "pointer",
  whiteSpace: "nowrap",
};

const disconnectBtn: React.CSSProperties = {
  ...connectBtn,
  background: "var(--red)",
};

const recentBtn: React.CSSProperties = {
  padding: "3px 10px",
  fontSize: 12,
  fontFamily: "'JetBrains Mono', monospace",
  background: "var(--bg-input)",
  border: "1px solid var(--border)",
  borderRadius: 4,
  color: "var(--text-secondary)",
  cursor: "pointer",
  whiteSpace: "nowrap",
};
