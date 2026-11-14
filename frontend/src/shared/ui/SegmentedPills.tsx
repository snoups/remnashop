import { motion } from "motion/react";
import { useId } from "react";

import { ActivePill } from "@shared/ui/ActivePill";
import { TAB_HOVER_CLASS } from "@shared/ui/classes";

export interface SegmentedPillsOption<T extends string | number> {
  value: T;
  label: string;
  /** unread dot in the corner, like the notifications bell's */
  dot?: boolean;
}

export function SegmentedPills<T extends string | number>({
  value,
  onChange,
  options,
  stretch = false,
  compact = false,
  panel = false,
  disabled = false,
}: {
  value: T;
  onChange: (value: T) => void;
  options: SegmentedPillsOption<T>[];
  /** fill the container, options share the width equally */
  stretch?: boolean;
  /** 36px instead of 38px, 14px text: beside other 36px controls (the notifications header) */
  compact?: boolean;
  /** the glass TabBar's 48px glass-panel capsule, 36px options: beside it in a page's floating bar */
  panel?: boolean;
  disabled?: boolean;
}) {
  const pillId = useId();

  return (
    <motion.div
      layoutScroll
      className={`no-scrollbar flex max-w-full shrink-0 gap-1 overflow-x-auto rounded-full ${
        panel ? "glass-panel h-12 p-1.5" : "border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md"
      } ${stretch ? "w-full" : ""}`}
    >
      {options.map((option) => (
        <motion.button
          key={option.value}
          type="button"
          disabled={disabled}
          onClick={() => onChange(option.value)}
          className={`group relative isolate whitespace-nowrap rounded-full disabled:cursor-not-allowed disabled:opacity-50 ${stretch ? "flex-1" : "shrink-0"}`}
        >
          {/* only the pill scales, so the label stays crisp */}
          {value === option.value ? (
            <ActivePill layoutId={pillId} />
          ) : (
            <span className={TAB_HOVER_CLASS} />
          )}
          <span
            className={`relative z-10 text-sm font-medium ${
              panel ? "flex h-9 items-center justify-center px-4" : `block px-3.5 ${compact ? "py-[3px] leading-5" : "py-1"}`
            } ${value === option.value ? "text-primary" : "text-foreground"}`}
          >
            {option.label}
          </span>
          {option.dot && <span className="absolute right-2.5 top-1.5 z-10 size-1.5 rounded-full bg-primary" />}
        </motion.button>
      ))}
    </motion.div>
  );
}
