import type { ReactNode } from "react";

/** A list row's text cell: a 14px title over a 12px muted subtitle, both truncated. className is layout only (flex-1, pl-4). */
export function CellText({
  title,
  sub,
  mono = false,
  className = "",
}: {
  title: ReactNode;
  /** omitted or empty: the title alone */
  sub?: ReactNode;
  /** a code, an id or a @username */
  mono?: boolean;
  className?: string;
}) {
  return (
    <span className={`min-w-0 ${className}`}>
      <span className="block truncate text-sm font-medium text-foreground">{title}</span>
      {sub && (
        <span className={`block truncate text-xs text-muted-foreground ${mono ? "font-mono" : ""}`}>{sub}</span>
      )}
    </span>
  );
}
