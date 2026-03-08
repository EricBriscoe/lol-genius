import type { LiveGameUpdate } from "../types";
import { fmtTime } from "../utils";

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

function fmtDiff(n: number): string {
  return n >= 0 ? `+${n}` : `${n}`;
}

export default function StatGrid({ data }: { data: LiveGameUpdate }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
      <StatBox label="Game Time" value={fmtTime(data.game_time)} />
      <StatBox label="Kill Diff" value={fmtDiff(data.kill_diff)} color={diffColor(data.kill_diff)} />
      <StatBox label="CS Diff" value={fmtDiff(data.cs_diff)} color={diffColor(data.cs_diff)} />
      <StatBox label="Tower Diff" value={fmtDiff(data.tower_diff)} color={diffColor(data.tower_diff)} />
      <StatBox label="Baron Diff" value={fmtDiff(data.baron_diff)} color={diffColor(data.baron_diff)} />
      <StatBox label="Dragon Diff" value={fmtDiff(data.dragon_diff)} color={diffColor(data.dragon_diff)} />
      <StatBox label="Inhibitor Diff" value={fmtDiff(data.inhibitor_diff)} color={diffColor(data.inhibitor_diff)} />
      <StatBox label="Elder Diff" value={fmtDiff(data.elder_diff)} color={diffColor(data.elder_diff)} />
    </div>
  );
}
