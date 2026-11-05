import type { ReactNode } from "react";

/** A list row's text cell: a 13px title over a 12px muted subtitle, both truncated. className is layout only (flex-1, pl-4). */
export function CellText({
  title,
  sub,
  mono = false,
  tabular = false,
  className = "",
}: {
  title: ReactNode;
  /** omitted or empty: the title alone */
  sub?: ReactNode;
  /** a code, an id or a @username */
  mono?: boolean;
  /** a subtitle of counts */
  tabular?: boolean;
  className?: string;
}) {
  return (
    <span className={`min-w-0 ${className}`}>
      <span className="block truncate text-[13px] font-medium text-foreground">{title}</span>
      {sub && (
        <span
          className={`block truncate text-[12px] text-muted-foreground ${mono ? "font-mono" : ""} ${tabular ? "tabular-nums" : ""}`}
        >
          {sub}
        </span>
      )}
    </span>
  );
}
