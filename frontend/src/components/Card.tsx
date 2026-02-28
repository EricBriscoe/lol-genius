import type { ReactNode, CSSProperties } from "react";

interface Props {
  children: ReactNode;
  style?: CSSProperties;
  glow?: boolean;
}

export default function Card({ children, style, glow }: Props) {
  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: `1px solid ${glow ? "var(--border-glow)" : "var(--border)"}`,
        borderRadius: 10,
        padding: 20,
        ...style,
      }}
    >
      {children}
    </div>
  );
}
