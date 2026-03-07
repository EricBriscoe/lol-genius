import type { CSSProperties } from "react";

export const tooltipStyle = {
  background: "var(--bg-secondary)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  fontSize: 12,
};

export const sectionTitle: CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: "var(--text-secondary)",
  textTransform: "uppercase",
  letterSpacing: "0.5px",
};

export const sectionLabel: CSSProperties = {
  fontSize: 10,
  fontWeight: 500,
  color: "var(--text-muted)",
  textTransform: "uppercase",
  letterSpacing: "1px",
};

export const primaryButton: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  padding: "8px 16px",
  fontSize: 13,
  fontWeight: 600,
  color: "var(--bg-primary)",
  background: "var(--accent)",
  border: "none",
  borderRadius: 6,
  cursor: "pointer",
  fontFamily: "inherit",
};

export const tableStyles = {
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: 13,
  },
  th: {
    textAlign: "left" as const,
    padding: "10px 12px",
    fontSize: 11,
    fontWeight: 600,
    color: "var(--text-muted)",
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
    borderBottom: "1px solid var(--border)",
    background: "var(--bg-secondary)",
  },
  tr: {
    cursor: "pointer",
    transition: "background 0.1s",
    borderBottom: "1px solid var(--border)",
  },
  td: {
    padding: "10px 12px",
    fontSize: 12,
  },
  tdMono: {
    padding: "10px 12px",
    fontSize: 12,
    fontFamily: "'JetBrains Mono', monospace",
  },
  closeBtn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: 28,
    height: 28,
    background: "var(--bg-primary)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    color: "var(--text-secondary)",
    cursor: "pointer",
  },
} satisfies Record<string, CSSProperties>;

export const inputStyle: CSSProperties = {
  padding: "8px 12px",
  fontSize: 13,
  background: "var(--bg-input)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  color: "var(--text-primary)",
  outline: "none",
  fontFamily: "inherit",
};

export const POSITION_LABELS: Record<string, string> = {
  TOP: "Top",
  JUNGLE: "Jungle",
  MIDDLE: "Mid",
  BOTTOM: "Bot",
  UTILITY: "Support",
};
