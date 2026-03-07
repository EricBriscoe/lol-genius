export default function WinProbBar({ blueProb }: { blueProb: number }) {
  const redProb = 100 - blueProb;
  return (
    <div style={{ margin: "16px 0 8px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13, fontWeight: 600 }}>
        <span style={{ color: "var(--accent)" }}>Blue {blueProb}%</span>
        <span style={{ color: "var(--red)" }}>Red {redProb}%</span>
      </div>
      <div style={{ height: 28, borderRadius: 8, overflow: "hidden", display: "flex" }}>
        <div style={{
          width: `${blueProb}%`,
          background: "var(--accent)",
          transition: "width 0.5s ease",
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          paddingRight: 8,
          fontSize: 12,
          fontWeight: 700,
          color: "var(--bg-primary)",
        }}>
          {blueProb > 20 && `${blueProb}%`}
        </div>
        <div style={{
          flex: 1,
          background: "var(--red)",
          display: "flex",
          alignItems: "center",
          paddingLeft: 8,
          fontSize: 12,
          fontWeight: 700,
          color: "var(--bg-primary)",
        }}>
          {redProb > 20 && `${redProb}%`}
        </div>
      </div>
    </div>
  );
}
