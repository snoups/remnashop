import { motion } from "motion/react";
import { useId } from "react";

import { ActivePill } from "@shared/ui/ActivePill";

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
  disabled = false,
  stretch = false,
  compact = false,
  panel = false,
}: {
  value: T;
  onChange: (value: T) => void;
  options: SegmentedPillsOption<T>[];
  disabled?: boolean;
  /** fill the container, options share the width equally */
  stretch?: boolean;
  /** 36px instead of 38px, 13px text: beside other 36px controls (the notifications header) */
  compact?: boolean;
  /** the glass TabBar's 48px glass-panel capsule, 36px options: beside it in a page's floating bar */
  panel?: boolean;
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
          className={`group relative isolate whitespace-nowrap rounded-full disabled:cursor-not-allowed ${stretch ? "flex-1" : "shrink-0"}`}
        >
          {/* only the pill scales, so the label stays crisp */}
          {value === option.value ? (
            <ActivePill layoutId={pillId} />
          ) : (
            <motion.span
              className="absolute inset-0 rounded-full transition-colors group-enabled:group-hover:bg-white/[0.06]"
            />
          )}
          <span
            className={`relative z-10 block font-medium ${
              panel ? "flex h-9 items-center px-4 text-[13px]" : compact ? "px-3.5 py-[3px] text-[13px] leading-5" : "px-3.5 py-1 text-[13px]"
            } ${
              value === option.value ? "text-primary" : "text-foreground"
            }`}
          >
            {option.label}
          </span>
          {option.dot && (
            <span className="absolute right-2.5 top-1.5 z-10 size-1.5 rounded-full bg-primary" />
          )}
        </motion.button>
      ))}
    </motion.div>
  );
}
