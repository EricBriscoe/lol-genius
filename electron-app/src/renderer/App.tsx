import { Wifi, WifiOff, AlertTriangle, RefreshCw, Bug } from "lucide-react";
import Card from "./components/Card";
import WinProbBar from "./components/WinProbBar";
import StatGrid from "./components/StatGrid";
import KeyFactors from "./components/KeyFactors";
import ProbChart from "./components/ProbChart";
import DevPanel from "./components/DevPanel";
import { useLiveGame } from "./hooks/useLiveGame";

export default function App() {
  const { connectionStatus, current, history, modelInfo, devMode, toggleDevMode, devLogs, clearDevLogs } = useLiveGame();

  const blueProb = current?.blue_win_probability != null
    ? Math.round(current.blue_win_probability * 100)
    : 50;

  const isConnected = connectionStatus === "ok" || connectionStatus === "connected";

  return (
    <div style={{ maxWidth: 880, margin: "0 auto", padding: "24px 20px", display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--text-primary)" }}>lol-genius</h1>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {modelInfo && (
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              Model: {modelInfo.version ?? "bundled"} ({modelInfo.featureCount} features)
            </span>
          )}
          <button
            onClick={() => window.lolGenius.checkForUpdates()}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 4 }}
            title="Check for model updates"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={toggleDevMode}
            style={{ background: "none", border: "none", cursor: "pointer", color: devMode ? "var(--accent)" : "var(--text-muted)", padding: 4 }}
            title={devMode ? "Disable developer mode" : "Enable developer mode"}
          >
            <Bug size={14} />
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {isConnected ? (
              <Wifi size={14} style={{ color: "var(--accent)" }} />
            ) : (
              <WifiOff size={14} style={{ color: "var(--text-muted)" }} />
            )}
            <span style={{ fontSize: 11, color: isConnected ? "var(--accent)" : "var(--text-muted)" }}>
              {isConnected ? "In Game" : connectionStatus === "no_data" ? "No Game" : "Connecting..."}
            </span>
          </div>
        </div>
      </div>

      {current && current.blue_win_probability != null && (
        <>
          <Card>
            <h3 style={sectionTitle}>Win Probability</h3>
            <WinProbBar blueProb={blueProb} />
          </Card>

          <StatGrid data={current} />
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
          <ProbChart data={history} />
        </Card>
      )}

      {connectionStatus === "model_missing" && (
        <Card style={{ borderColor: "var(--red)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", color: "var(--red)", fontSize: 13 }}>
            <AlertTriangle size={16} />
            No model found. Train a live model and export it, or check for model updates.
          </div>
        </Card>
      )}

      {connectionStatus === "no_data" && (
        <Card style={{ borderColor: "var(--gold)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", color: "var(--gold)", fontSize: 13 }}>
            <AlertTriangle size={16} />
            No game detected — start a League match to see predictions
          </div>
        </Card>
      )}

      {!current && connectionStatus === "connecting" && (
        <Card>
          <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-muted)" }}>
            <div style={{ fontSize: 14, marginBottom: 8 }}>Waiting for game...</div>
            <div style={{ fontSize: 12 }}>Polls localhost:2999 every 15 seconds</div>
          </div>
        </Card>
      )}

      {devMode && <DevPanel logs={devLogs} onClear={clearDevLogs} />}
    </div>
  );
}

const sectionTitle: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: "var(--text-secondary)",
  textTransform: "uppercase",
  letterSpacing: "0.5px",
};
