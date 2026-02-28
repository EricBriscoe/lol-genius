interface Props {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}

export default function StatBox({ label, value, sub, color = "var(--text-primary)" }: Props) {
  return (
    <div style={{ textAlign: "center", minWidth: 120 }}>
      <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 6 }}>
        {label}
      </div>
      <div className="mono" style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1 }}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      {sub && (
        <div className="mono" style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>
          {sub}
        </div>
      )}
    </div>
  );
}
