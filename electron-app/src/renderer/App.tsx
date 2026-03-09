import { useState, useEffect } from "react";
import { Monitor, MonitorOff, AlertTriangle, RefreshCw, Bug, Swords, Gamepad2, Pin } from "lucide-react";
import Card from "./components/Card";
import WinProbBar from "./components/WinProbBar";
import StatGrid from "./components/StatGrid";
import KeyFactors from "./components/KeyFactors";
import ProbChart from "./components/ProbChart";
import DevPanel from "./components/DevPanel";
import ChampSelect from "./components/ChampSelect";
import { useLiveGame } from "./hooks/useLiveGame";
import { useChampSelect } from "./hooks/useChampSelect";
import type { AppUpdateEvent } from "./types";
import { sectionTitle } from "./styles";
import { toBlueProb } from "./utils";

export default function App() {
  const { connectionStatus, current, history, modelInfo, devMode, toggleDevMode, devLogs, clearDevLogs, appUpdateStatus } = useLiveGame();
  const [appVersion, setAppVersion] = useState<string | null>(null);
  const [alwaysOnTop, setAlwaysOnTop] = useState(false);

  useEffect(() => {
    window.lolGenius.getAppVersion().then(setAppVersion);
    window.lolGenius.getAlwaysOnTop().then(setAlwaysOnTop);
  }, []);

  const toggleAlwaysOnTop = async () => {
    const next = !alwaysOnTop;
    await window.lolGenius.setAlwaysOnTop(next);
    setAlwaysOnTop(next);
  };
  const { champSelectData, isInChampSelect } = useChampSelect();

  const blueProb = toBlueProb(current?.blue_win_probability);

  const isInGame = connectionStatus === "ok" || connectionStatus === "connected";

  const phase = isInChampSelect ? "champ_select" : isInGame ? "in_game" : "idle";

  return (
    <>
    <div style={{ maxWidth: 880, margin: "0 auto", padding: "24px 20px", display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--text-primary)" }}>lol-genius</h1>
          {appVersion && <span style={{ fontSize: 11, color: "var(--text-muted)" }}>v{appVersion}</span>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {modelInfo && (
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              Model: {modelInfo.version ?? "bundled"} ({modelInfo.featureCount} features)
            </span>
          )}
          <button
            onClick={() => { window.lolGenius.checkForUpdates(); window.lolGenius.checkAppUpdates(); }}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 4 }}
            title="Check for updates"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={toggleAlwaysOnTop}
            style={{ background: "none", border: "none", cursor: "pointer", color: alwaysOnTop ? "var(--accent)" : "var(--text-muted)", padding: 4 }}
            title={alwaysOnTop ? "Unpin window" : "Pin window on top"}
          >
            <Pin size={14} />
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

      {phase === "in_game" && !current && (
        <Card>
          <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-muted)" }}>
            <div style={{ fontSize: 14, marginBottom: 8 }}>Game detected</div>
            <div style={{ fontSize: 12 }}>Waiting for first prediction...</div>
          </div>
        </Card>
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
    <UpdateBanner event={appUpdateStatus} />
  </>
  );
}

function UpdateBanner({ event }: { event: AppUpdateEvent | null }) {
  const [dismissed, setDismissed] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (event?.status === "error") {
      setDismissed(false);
      setVisible(true);
      const timer = setTimeout(() => setDismissed(true), 5000);
      return () => clearTimeout(timer);
    }
    if (event?.status === "downloading" || event?.status === "downloaded") {
      setDismissed(false);
      setVisible(true);
    }
  }, [event]);

  useEffect(() => {
    if (!event || dismissed) setVisible(false);
  }, [event, dismissed]);

  const show = !!event && !dismissed;
  if (!show && !visible) return null;

  const { status } = event!;
  const slideStyle: React.CSSProperties = {
    ...toastStyle,
    transform: show ? "translateY(0)" : "translateY(20px)",
    opacity: show ? 1 : 0,
    pointerEvents: show ? "auto" : "none",
    ...(status === "downloaded" ? { display: "flex", alignItems: "center", gap: 6 } : {}),
  };

  const color = status === "downloading" ? "var(--accent)" : status === "downloaded" ? "var(--green)" : "var(--text-muted)";

  return (
    <div style={slideStyle}>
      <span style={{ color }}>
        {status === "downloading" && `↓ Updating… ${event!.percent}%`}
        {status === "downloaded" && "Update ready"}
        {status === "error" && "Update failed"}
      </span>
      {status === "downloaded" && (
        <>
          <span style={{ color: "var(--text-muted)" }}>·</span>
          <button onClick={() => window.lolGenius.installAppUpdate()} style={restartBtnStyle}>Restart</button>
        </>
      )}
    </div>
  );
}

function PhaseChip({ icon: Icon, color, label }: { icon: React.ElementType; color: string; label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <Icon size={14} style={{ color }} />
      <span style={{ fontSize: 11, color }}>{label}</span>
    </div>
  );
}

function GamePhaseIndicator({ phase, connectionStatus }: { phase: string; connectionStatus: string }) {
  if (phase === "champ_select") return <PhaseChip icon={Swords} color="var(--gold)" label="Champ Select" />;
  if (phase === "in_game") return <PhaseChip icon={Gamepad2} color="var(--accent)" label="In Game" />;

  const label = connectionStatus === "lcu_connected" ? "Client Connected" : connectionStatus === "connecting" ? "Connecting..." : "No Game";
  const Icon = connectionStatus === "lcu_connected" ? Monitor : MonitorOff;
  return <PhaseChip icon={Icon} color="var(--text-muted)" label={label} />;
}

const toastStyle: React.CSSProperties = {
  position: "fixed",
  bottom: 16,
  right: 16,
  maxWidth: 240,
  padding: "6px 12px",
  borderRadius: 20,
  fontSize: 11,
  fontWeight: 500,
  zIndex: 9999,
  backdropFilter: "blur(12px)",
  WebkitBackdropFilter: "blur(12px)",
  background: "rgba(30,30,30,0.85)",
  transition: "transform 0.3s ease, opacity 0.3s ease",
};

const restartBtnStyle: React.CSSProperties = {
  background: "none",
  border: "none",
  padding: 0,
  color: "var(--green)",
  fontSize: 11,
  fontWeight: 600,
  cursor: "pointer",
  textDecoration: "underline",
};

