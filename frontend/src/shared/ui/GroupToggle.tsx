import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

interface GroupToggleProps {
  open: boolean;
  onToggle: () => void;
  label: ReactNode;
  count: number;
  /** before the label (a status dot) */
  leading?: ReactNode;
}

/** Header of a collapsible list group (a day, a status); the caller wraps it in <h3> where it heads a section. */
export function GroupToggle({ open, onToggle, label, count, leading }: GroupToggleProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="group flex w-full items-center gap-2.5 rounded-full px-3 py-1.5 text-left"
    >
      <ChevronDown
        className={`size-3.5 text-muted-foreground transition-transform group-hover:text-foreground ${
          open ? "" : "-rotate-90"
        }`}
      />
      {leading}
      <span className="-ml-1 text-[12px] font-semibold text-foreground">{label}</span>
      <span className="-ml-1 text-[12px] tabular-nums text-muted-foreground">{count}</span>
    </button>
  );
}
