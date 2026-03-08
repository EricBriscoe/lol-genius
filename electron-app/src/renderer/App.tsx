import { Wifi, WifiOff, AlertTriangle, RefreshCw, Bug, Swords, Gamepad2 } from "lucide-react";
import Card from "./components/Card";
import WinProbBar from "./components/WinProbBar";
import StatGrid from "./components/StatGrid";
import KeyFactors from "./components/KeyFactors";
import ProbChart from "./components/ProbChart";
import DevPanel from "./components/DevPanel";
import ChampSelect from "./components/ChampSelect";
import { useLiveGame } from "./hooks/useLiveGame";
import { useChampSelect } from "./hooks/useChampSelect";
import { sectionTitle } from "./styles";

export default function App() {
  const { connectionStatus, current, history, modelInfo, devMode, toggleDevMode, devLogs, clearDevLogs } = useLiveGame();
  const { champSelectData, isInChampSelect } = useChampSelect();

  const blueProb = current?.blue_win_probability != null
    ? Math.round(current.blue_win_probability * 100)
    : 50;

  const isInGame = connectionStatus === "ok" || connectionStatus === "connected";

  const phase = isInChampSelect ? "champ_select" : isInGame ? "in_game" : "idle";

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
          <GamePhaseIndicator phase={phase} connectionStatus={connectionStatus} />
        </div>
      </div>

      {phase === "champ_select" && champSelectData && (
        <ChampSelect data={champSelectData} />
      )}

      {phase === "in_game" && current && current.blue_win_probability != null && (
        <>
          <Card>
            <h3 style={sectionTitle}>Win Probability</h3>
            <WinProbBar blueProb={blueProb} />
          </Card>

          <StatGrid data={current} />
        </>
      )}

      {phase === "in_game" && current?.top_factors && current.top_factors.length > 0 && (
        <Card>
          <h3 style={sectionTitle}>Key Factors</h3>
          <KeyFactors factors={current.top_factors} />
        </Card>
      )}

      {phase === "in_game" && history.length > 1 && (
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

      {phase === "idle" && connectionStatus !== "model_missing" && (
        <Card style={{ borderColor: "var(--gold)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", color: "var(--gold)", fontSize: 13 }}>
            <AlertTriangle size={16} />
            No game detected — open League client or start a match to see predictions
          </div>
        </Card>
      )}

      {!current && phase === "idle" && connectionStatus === "connecting" && (
        <Card>
          <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-muted)" }}>
            <div style={{ fontSize: 14, marginBottom: 8 }}>Waiting for game...</div>
            <div style={{ fontSize: 12 }}>Monitoring League client and live game</div>
          </div>
        </Card>
      )}

      {devMode && <DevPanel logs={devLogs} onClear={clearDevLogs} />}
    </div>
  );
}

function GamePhaseIndicator({ phase, connectionStatus }: { phase: string; connectionStatus: string }) {
  if (phase === "champ_select") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Swords size={14} style={{ color: "var(--gold)" }} />
        <span style={{ fontSize: 11, color: "var(--gold)" }}>Champ Select</span>
      </div>
    );
  }

  if (phase === "in_game") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Gamepad2 size={14} style={{ color: "var(--accent)" }} />
        <span style={{ fontSize: 11, color: "var(--accent)" }}>In Game</span>
      </div>
    );
  }

  const isConnecting = connectionStatus === "connecting";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      {connectionStatus === "lcu_connected" ? (
        <>
          <Wifi size={14} style={{ color: "var(--text-muted)" }} />
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Client Connected</span>
        </>
      ) : (
        <>
          <WifiOff size={14} style={{ color: "var(--text-muted)" }} />
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
            {isConnecting ? "Connecting..." : "No Game"}
          </span>
        </>
      )}
    </div>
  );
}

