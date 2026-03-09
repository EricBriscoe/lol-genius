import { useState, useEffect } from "react";
import { Monitor, MonitorOff, AlertTriangle, RefreshCw, Bug, Swords, Gamepad2, Pin, User } from "lucide-react";
import Card from "./components/Card";
import WinProbBar from "./components/WinProbBar";
import StatGrid from "./components/StatGrid";
import KeyFactors from "./components/KeyFactors";
import ProbChart from "./components/ProbChart";
import DevPanel from "./components/DevPanel";
import ChampSelect from "./components/ChampSelect";
import PlayerInfo from "./components/PlayerInfo";
import { useLiveGame } from "./hooks/useLiveGame";
import { useChampSelect } from "./hooks/useChampSelect";
import type { AppUpdateEvent } from "./types";
import { toBlueProb } from "./utils";

type TabId = "game" | "player_info";

export default function App() {
  const { connectionStatus, current, history, modelInfo, devMode, toggleDevMode, devLogs, clearDevLogs, appUpdateStatus } = useLiveGame();
  const [appVersion, setAppVersion] = useState<string | null>(null);
  const [alwaysOnTop, setAlwaysOnTop] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>(() =>
    (localStorage.getItem("activeTab") as TabId) || "game"
  );

  useEffect(() => {
    window.lolGenius.getAppVersion().then(setAppVersion);
    window.lolGenius.getAlwaysOnTop().then(setAlwaysOnTop);
  }, []);

  useEffect(() => {
    localStorage.setItem("activeTab", activeTab);
  }, [activeTab]);

  const toggleAlwaysOnTop = async () => {
    const next = !alwaysOnTop;
    await window.lolGenius.setAlwaysOnTop(next);
    setAlwaysOnTop(next);
  };
  const { champSelectData, isInChampSelect } = useChampSelect();

  const blueProb = toBlueProb(current?.blue_win_probability);
  const isInGame = connectionStatus === "ok" || connectionStatus === "connected";
  const phase = isInChampSelect ? "champ_select" : isInGame ? "in_game" : "idle";

  useEffect(() => {
    if (phase === "champ_select" || phase === "in_game") {
      setActiveTab("game");
    }
  }, [phase]);

  return (
    <>
    <div className="app-container">
      <div className="app-header">
        <div className="app-header__title-group">
          <h1 className="app-header__title">lol-genius</h1>
          {appVersion && <span className="app-header__version">v{appVersion}</span>}
        </div>
        <div className="app-header__controls">
          {modelInfo && (
            <span className="app-header__model-info">
              Model: {modelInfo.version ?? "bundled"} ({modelInfo.featureCount} features)
            </span>
          )}
          <button
            onClick={() => { window.lolGenius.checkForUpdates(); }}
            className="icon-btn"
            title="Check for updates"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={toggleAlwaysOnTop}
            className={`icon-btn${alwaysOnTop ? " icon-btn--active" : ""}`}
            title={alwaysOnTop ? "Unpin window" : "Pin window on top"}
          >
            <Pin size={14} />
          </button>
          <button
            onClick={toggleDevMode}
            className={`icon-btn${devMode ? " icon-btn--active" : ""}`}
            title={devMode ? "Disable developer mode" : "Enable developer mode"}
          >
            <Bug size={14} />
          </button>
          <GamePhaseIndicator phase={phase} connectionStatus={connectionStatus} />
        </div>
      </div>

      <div className="tab-bar">
        <button
          className={`tab-bar__tab ${activeTab === "game" ? "tab-bar__tab--active" : ""}`}
          onClick={() => setActiveTab("game")}
        >
          <Gamepad2 size={14} />
          Game
        </button>
        <button
          className={`tab-bar__tab ${activeTab === "player_info" ? "tab-bar__tab--active" : ""}`}
          onClick={() => setActiveTab("player_info")}
        >
          <User size={14} />
          Player Info
        </button>
      </div>

      {activeTab === "game" && (
        <>
          {phase === "champ_select" && champSelectData && (
            <ChampSelect data={champSelectData} />
          )}

          {phase === "in_game" && !current && (
            <Card>
              <div className="waiting-state">
                <div className="waiting-state__title">Game detected</div>
                <div className="waiting-state__subtitle">Waiting for first prediction...</div>
              </div>
            </Card>
          )}

          {phase === "in_game" && current && current.blue_win_probability != null && (
            <>
              <Card>
                <h3 className="section-title">Win Probability</h3>
                <WinProbBar blueProb={blueProb} />
              </Card>

              <StatGrid data={current} />
            </>
          )}

          {phase === "in_game" && current?.top_factors && current.top_factors.length > 0 && (
            <Card>
              <h3 className="section-title">Key Factors</h3>
              <KeyFactors factors={current.top_factors} />
            </Card>
          )}

          {phase === "in_game" && history.length > 1 && (
            <Card>
              <h3 className="section-title">Win Probability History</h3>
              <ProbChart data={history} />
            </Card>
          )}

          {connectionStatus === "model_missing" && (
            <Card variant="error">
              <div className="alert-message alert-message--error">
                <AlertTriangle size={16} />
                No model found. Train a live model and export it, or check for model updates.
              </div>
            </Card>
          )}

          {phase === "idle" && connectionStatus !== "model_missing" && (
            <Card variant="warning">
              <div className="alert-message alert-message--warning">
                <AlertTriangle size={16} />
                No game detected — open League client or start a match to see predictions
              </div>
            </Card>
          )}

          {!current && phase === "idle" && connectionStatus === "connecting" && (
            <Card>
              <div className="waiting-state">
                <div className="waiting-state__title">Waiting for game...</div>
                <div className="waiting-state__subtitle">Monitoring League client and live game</div>
              </div>
            </Card>
          )}
        </>
      )}

      {activeTab === "player_info" && <PlayerInfo />}

      {devMode && <DevPanel logs={devLogs} onClear={clearDevLogs} />}
    </div>
    <UpdateBanner event={appUpdateStatus} />
  </>
  );
}

function UpdateBanner({ event }: { event: AppUpdateEvent | null }) {
  const [visible, setVisible] = useState(false);

  const status = event?.status;
  const show = status === "downloading" || status === "restarting";

  useEffect(() => {
    if (show) setVisible(true);
    else { const t = setTimeout(() => setVisible(false), 300); return () => clearTimeout(t); }
  }, [show]);

  if (!show && !visible) return null;

  const color = status === "downloading" ? "var(--accent)" : "var(--green)";

  return (
    <div className="toast" style={{ transform: show ? "translateY(0)" : "translateY(20px)", opacity: show ? 1 : 0 }}>
      <span style={{ color }}>
        {status === "downloading" && `Updating… ${(event as { percent: number }).percent}%`}
        {status === "restarting" && "Restarting to update…"}
      </span>
    </div>
  );
}

function PhaseChip({ icon: Icon, color, label }: { icon: React.ElementType; color: string; label: string }) {
  return (
    <div className="phase-chip">
      <Icon size={14} style={{ color }} />
      <span className="phase-chip__label" style={{ color }}>{label}</span>
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
