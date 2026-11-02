import type { ReactNode } from "react";

/** 32px sunken label in a Row: a count or a state next to its control. */
export function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="glass-well flex h-8 shrink-0 items-center rounded-full px-3 text-[11px] font-medium text-muted-foreground">
      {children}
    </span>
  );
}
