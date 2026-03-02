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
import { Wifi, WifiOff, Play, Square } from "lucide-react";
import Card from "../components/Card";
import { startLiveGame, stopLiveGame, fetchLiveGameStatus } from "../api";
import { sectionTitle } from "../styles";
import type { LiveGameUpdate, LiveGameStatus } from "../types";

interface Props {
  latestUpdate: LiveGameUpdate | null;
}

function fmtTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
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

export default function LiveGame({ latestUpdate }: Props) {
  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState("2999");
  const [connected, setConnected] = useState(false);
  const [history, setHistory] = useState<{ game_time: number; probability: number }[]>([]);
  const [current, setCurrent] = useState<LiveGameUpdate | null>(null);

  useEffect(() => {
    fetchLiveGameStatus().then((s: LiveGameStatus) => {
      setConnected(s.connected);
      if (s.host) setHost(s.host);
      if (s.port) setPort(String(s.port));
      setHistory(s.history);
      setCurrent(s.current);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!latestUpdate) return;
    setCurrent(latestUpdate);
    setHistory((prev) => {
      const entry = { game_time: latestUpdate.game_time, probability: Math.round(latestUpdate.blue_win_probability * 100 * 10) / 10 };
      if (prev.length > 0 && prev[prev.length - 1].game_time === entry.game_time) return prev;
      const next = [...prev, entry];
      return next.length > 100 ? next.slice(-100) : next;
    });
  }, [latestUpdate]);

  async function handleConnect() {
    const portNum = Number(port);
    if (isNaN(portNum) || portNum < 1 || portNum > 65535) return;
    try {
      await startLiveGame(host, portNum);
      setConnected(true);
      setHistory([]);
      setCurrent(null);
    } catch {}
  }

  async function handleDisconnect() {
    try {
      await stopLiveGame();
      setConnected(false);
    } catch {}
  }

  const blueProb = current ? Math.round(current.blue_win_probability * 100) : 50;
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
        {!connected && (
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 10 }}>
            Connect to the Riot Live Client Data API (LoL must be running). Polls every 15s and predicts with the live model.
          </p>
        )}
      </Card>

      {current && (
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

          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12 }}>
            <StatBox label="Game Time" value={fmtTime(current.game_time)} />
            <StatBox
              label="Gold Diff"
              value={current.gold_diff >= 0 ? `+${current.gold_diff}` : current.gold_diff}
              color={current.gold_diff > 0 ? "var(--accent)" : current.gold_diff < 0 ? "var(--red)" : undefined}
            />
            <StatBox
              label="Kill Diff"
              value={current.kill_diff >= 0 ? `+${current.kill_diff}` : current.kill_diff}
              color={current.kill_diff > 0 ? "var(--accent)" : current.kill_diff < 0 ? "var(--red)" : undefined}
            />
            <StatBox
              label="Dragon Diff"
              value={current.dragon_diff >= 0 ? `+${current.dragon_diff}` : current.dragon_diff}
              color={current.dragon_diff > 0 ? "var(--accent)" : current.dragon_diff < 0 ? "var(--red)" : undefined}
            />
            <StatBox
              label="Tower Diff"
              value={current.tower_diff >= 0 ? `+${current.tower_diff}` : current.tower_diff}
              color={current.tower_diff > 0 ? "var(--accent)" : current.tower_diff < 0 ? "var(--red)" : undefined}
            />
            <StatBox label="Blue Barons" value={current.blue_barons} />
          </div>
        </>
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
                  formatter={(v: number) => [`${v}%`, "Blue Win %"]}
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

      {connected && !current && (
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
