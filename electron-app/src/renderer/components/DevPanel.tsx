import { useEffect, useRef, type CSSProperties } from "react";
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
    <div style={container}>
      <div style={header}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
          Debug Log
        </span>
        <button onClick={onClear} style={clearBtn}>Clear</button>
      </div>
      <div ref={scrollRef} style={logArea}>
        {logs.length === 0 && (
          <div style={{ color: "var(--text-muted)", fontSize: 11, padding: 8 }}>
            Waiting for log entries...
          </div>
        )}
        {logs.map((entry, i) => (
          <div key={i} style={logLine}>
            <span style={{ color: "var(--text-muted)" }}>
              {entry.timestamp.slice(11, 23)}
            </span>
            {entry.scope && (
              <span style={{ color: "#8b949e" }}>[{entry.scope}]</span>
            )}
            <span style={{ color: LEVEL_COLORS[entry.level] ?? "var(--text-primary)" }}>
              {entry.message}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const container: CSSProperties = {
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  borderRadius: 10,
  overflow: "hidden",
};

const header: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  padding: "10px 16px",
  borderBottom: "1px solid var(--border)",
};

const clearBtn: CSSProperties = {
  background: "none",
  border: "1px solid var(--border)",
  borderRadius: 4,
  color: "var(--text-muted)",
  cursor: "pointer",
  fontSize: 10,
  padding: "2px 8px",
};

const logArea: CSSProperties = {
  height: 200,
  overflowY: "auto",
  padding: "4px 12px",
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  fontSize: 11,
  lineHeight: 1.6,
};

const logLine: CSSProperties = {
  display: "flex",
  gap: 8,
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};
