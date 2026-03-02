import { useState, useCallback, useEffect } from "react";
import { Activity, Brain, Crosshair, Gamepad2 } from "lucide-react";
import { fetchTrainingStatus } from "./api";
import { useSSE } from "./hooks/useSSE";
import CrawlerStatus from "./pages/CrawlerStatus";
import ModelTraining from "./pages/ModelTraining";
import LivePredict from "./pages/LivePredict";
import LiveGame from "./pages/LiveGame";
import type { CrawlerSSE, TrainingStatus, LiveGameUpdate } from "./types";
import { isCrawlerSSE, isTrainingStatus, isLiveGameUpdate } from "./types";

const TABS = [
  { id: "crawler", label: "Crawler", icon: Activity },
  { id: "model", label: "Model", icon: Brain },
  { id: "predict", label: "Predict", icon: Crosshair },
  { id: "live", label: "Live Game", icon: Gamepad2 },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function App() {
  const [tab, setTab] = useState<TabId>("crawler");
  const [crawlerData, setCrawlerData] = useState<CrawlerSSE | null>(null);
  const [trainingStatus, setTrainingStatus] = useState<TrainingStatus | null>(null);
  const [liveGameUpdate, setLiveGameUpdate] = useState<LiveGameUpdate | null>(null);

  useEffect(() => {
    fetchTrainingStatus().then((s) => {
      if (s.stage !== "idle") setTrainingStatus(s);
    }).catch(() => {});
  }, []);

  const handleCrawlerStatus = useCallback((data: unknown) => {
    if (isCrawlerSSE(data)) setCrawlerData(data);
  }, []);

  const handleTrainingStatus = useCallback((data: unknown) => {
    if (isTrainingStatus(data)) setTrainingStatus(data);
  }, []);

  const handleLiveGameUpdate = useCallback((data: unknown) => {
    if (isLiveGameUpdate(data)) setLiveGameUpdate(data);
  }, []);

  const connected = useSSE({
    crawler_status: handleCrawlerStatus,
    training_status: handleTrainingStatus,
    live_game_update: handleLiveGameUpdate,
  });

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.logo}>lol-genius</span>
          <span style={styles.badge}>DASHBOARD</span>
        </div>
        <nav style={styles.nav}>
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                ...styles.tab,
                ...(tab === t.id ? styles.tabActive : {}),
              }}
            >
              <t.icon size={16} />
              {t.label}
            </button>
          ))}
        </nav>
        <div style={styles.headerRight}>
          <span
            style={{
              ...styles.dot,
              background: connected ? "var(--accent)" : "var(--red)",
            }}
          />
          <span className="mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            {connected ? "LIVE" : "DISCONNECTED"}
          </span>
        </div>
      </header>

      <main style={styles.main}>
        {tab === "crawler" && <CrawlerStatus live={crawlerData} crawlerMode={crawlerData?.crawler_mode} />}
        {tab === "model" && <ModelTraining trainingStatus={trainingStatus} />}
        {tab === "predict" && <LivePredict />}
        {tab === "live" && <LiveGame latestUpdate={liveGameUpdate} />}
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 24px",
    height: 56,
    borderBottom: "1px solid var(--border)",
    background: "var(--bg-secondary)",
    flexShrink: 0,
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  logo: {
    fontFamily: "'JetBrains Mono', monospace",
    fontWeight: 700,
    fontSize: 16,
    color: "var(--accent)",
    letterSpacing: "-0.5px",
  },
  badge: {
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "1.5px",
    color: "var(--text-muted)",
    padding: "2px 6px",
    border: "1px solid var(--border)",
    borderRadius: 4,
  },
  nav: {
    display: "flex",
    gap: 4,
  },
  tab: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "8px 16px",
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text-secondary)",
    background: "transparent",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    transition: "all 0.15s",
    fontFamily: "inherit",
  },
  tabActive: {
    color: "var(--text-primary)",
    background: "var(--bg-card)",
    boxShadow: "inset 0 0 0 1px var(--border)",
  },
  headerRight: {
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    display: "inline-block",
  },
  main: {
    flex: 1,
    padding: 24,
    overflow: "auto",
  },
};
