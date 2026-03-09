import type { LiveGameUpdate } from "../types";
import { fmtTime } from "../utils";

function diffColor(diff: number): string | undefined {
  return diff > 0 ? "var(--accent)" : diff < 0 ? "var(--red)" : undefined;
}

function StatBox({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="stat-box">
      <div className="stat-box__label">{label}</div>
      <div className="stat-box__value" style={color ? { color } : undefined}>{value}</div>
    </div>
  );
}

function fmtDiff(n: number): string {
  return n >= 0 ? `+${n}` : `${n}`;
}

export default function StatGrid({ data }: { data: LiveGameUpdate }) {
  return (
    <div className="stat-grid">
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
