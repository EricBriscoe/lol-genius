import type { ReactNode, CSSProperties } from "react";

export default function Card({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{
      background: "var(--bg-card)",
      border: "1px solid var(--border)",
      borderRadius: 10,
      padding: 20,
      ...style,
    }}>
      {children}
    </div>
  );
}
