import { useEffect, useRef } from "react";
import type { DevLogEntry } from "../types";

const LEVEL_COLORS: Record<string, string> = {
  debug: "var(--text-muted)",
  info: "#5b9bd5",
  warn: "var(--gold)",
  error: "var(--red)",
};

export default function DevPanel({
  logs,
  onClear,
}: {
  logs: DevLogEntry[];
  onClear: () => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs.length]);

  return (
    <div className="dev-panel">
      <div className="dev-panel__header">
        <span className="dev-panel__title">Debug Log</span>
        <button onClick={onClear} className="btn-clear dev-panel__clear-btn">Clear</button>
      </div>
      <div ref={scrollRef} className="dev-panel__log-area">
        {logs.length === 0 && (
          <div className="dev-panel__empty">Waiting for log entries...</div>
        )}
        {logs.map((entry, i) => (
          <div key={i} className="dev-panel__log-line">
            <span className="dev-panel__timestamp">{entry.timestamp.slice(11, 23)}</span>
            {entry.scope && <span className="dev-panel__scope">[{entry.scope}]</span>}
            <span style={{ color: LEVEL_COLORS[entry.level] ?? "var(--text-primary)" }}>{entry.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
