export default function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{label}</span>
      <span className="mono" style={{ fontSize: 12, color: "var(--text-primary)" }}>{value}</span>
    </div>
  );
}
