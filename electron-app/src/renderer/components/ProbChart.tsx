import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

function fmtTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  data: { game_time: number; probability: number }[];
}

export default function ProbChart({ data }: Props) {
  return (
    <div style={{ height: 240, marginTop: 12 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="game_time"
            tickFormatter={fmtTime}
            tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
            label={{ value: "Game Time", position: "insideBottom", offset: -2, fill: "var(--text-muted)", fontSize: 11 }}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
            tickFormatter={(v: number) => `${v}%`}
          />
          <Tooltip
            contentStyle={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 12 }}
            formatter={(v) => [`${v ?? 0}%`, "Blue Win %"]}
            labelFormatter={fmtTime}
          />
          <ReferenceLine y={50} stroke="var(--text-muted)" strokeDasharray="4 4" />
          <Line
            type="monotone"
            dataKey="probability"
            stroke="var(--accent)"
            strokeWidth={2}
            dot={{ fill: "var(--accent)", r: 3 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
