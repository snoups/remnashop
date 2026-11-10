import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

import { Ripple } from "@shared/ui/Ripple";

interface GroupToggleProps {
  open: boolean;
  onToggle: () => void;
  label: ReactNode;
  count: number;
  /** before the label (a status dot) */
  leading?: ReactNode;
  /** over glass ListRows: 14px in, the chevron over their circles */
  glass?: boolean;
}

/** Header of a collapsible list group (a day, a status); the caller wraps it in <h3> where it heads a section. */
export function GroupToggle({ open, onToggle, label, count, leading, glass = false }: GroupToggleProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`group relative flex w-full items-center gap-2.5 rounded-full py-1.5 text-left ${glass ? "px-3.5" : "px-3"}`}
    >
      <Ripple />
      <ChevronDown
        className={`size-3.5 text-muted-foreground transition-transform group-hover:text-foreground ${
          open ? "" : "-rotate-90"
        }`}
      />
      {leading}
      <span className="-ml-1 text-xs font-semibold text-foreground">{label}</span>
      <span className="-ml-1 text-xs tabular-nums text-muted-foreground">{count}</span>
    </button>
  );
}
