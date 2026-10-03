import { motion } from "motion/react";
import { useId } from "react";

import { TAP_PILL_SCALE } from "@shared/lib/bounceState";
import { ActivePill } from "@shared/ui/ActivePill";

export interface SegmentedPillsOption<T extends string | number> {
  value: T;
  label: string;
  /** red unread dot in the corner, like the notifications bell's */
  dot?: boolean;
}

export function SegmentedPills<T extends string | number>({
  value,
  onChange,
  options,
  disabled = false,
  stretch = false,
}: {
  value: T;
  onChange: (value: T) => void;
  options: SegmentedPillsOption<T>[];
  disabled?: boolean;
  /** fill the container, options share the width equally */
  stretch?: boolean;
}) {
  const pillId = useId();

  return (
    <motion.div
      layoutScroll
      className={`no-scrollbar flex max-w-full shrink-0 gap-1 overflow-x-auto rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md ${stretch ? "w-full" : ""}`}
    >
      {options.map((option) => (
        <motion.button
          key={option.value}
          type="button"
          disabled={disabled}
          onClick={() => onChange(option.value)}
          initial="rest"
          whileTap="tap"
          className={`group relative isolate whitespace-nowrap rounded-full disabled:cursor-not-allowed ${stretch ? "flex-1" : "shrink-0"}`}
        >
          {/* only the pill scales, so the label stays crisp */}
          {value === option.value ? (
            <ActivePill layoutId={pillId} />
          ) : (
            <motion.span
              variants={{ rest: { scale: 1 }, tap: { scale: TAP_PILL_SCALE } }}
              className="absolute inset-0 rounded-full transition-colors group-enabled:group-hover:bg-white/[0.06]"
            />
          )}
          <span
            className={`relative z-10 block px-3.5 py-1 text-sm font-medium ${
              value === option.value ? "text-primary" : "text-foreground"
            }`}
          >
            {option.label}
          </span>
          {option.dot && (
            <span className="absolute right-2.5 top-1.5 z-10 size-1.5 rounded-full bg-error" aria-hidden />
          )}
        </motion.button>
      ))}
    </motion.div>
  );
}
