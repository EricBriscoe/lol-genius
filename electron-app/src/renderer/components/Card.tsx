import type { ReactNode } from "react";

export default function Card({ children, variant, className }: {
  children: ReactNode;
  variant?: "error" | "warning";
  className?: string;
}) {
  const cls = ["card", variant && `card--${variant}`, className].filter(Boolean).join(" ");
  return <div className={cls}>{children}</div>;
}
