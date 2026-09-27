import { motion } from "motion/react";

import { useBounceStrength } from "@shared/lib/bounceState";

export interface SegmentedPillsOption<T extends string | number> {
  value: T;
  label: string;
}

export function SegmentedPills<T extends string | number>({
  value,
  onChange,
  options,
  ariaLabel,
  disabled = false,
}: {
  value: T;
  onChange: (value: T) => void;
  options: SegmentedPillsOption<T>[];
  ariaLabel: string;
  disabled?: boolean;
}) {
  const bounceStrength = useBounceStrength();

  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className="no-scrollbar flex max-w-full shrink-0 gap-1 overflow-x-auto rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md"
    >
      {options.map((option) => (
        <motion.button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          disabled={disabled}
          onClick={() => onChange(option.value)}
          initial="rest"
          whileTap="tap"
          className="group relative isolate shrink-0 whitespace-nowrap rounded-full disabled:cursor-not-allowed"
        >
          {/* only the pill scales, so the label stays crisp */}
          <motion.span
            aria-hidden
            variants={{ rest: { scale: 1 }, tap: { scale: 1 + 0.05 * bounceStrength } }}
            className={`absolute inset-0 rounded-full transition-colors ${
              value === option.value ? "bg-accent" : "group-enabled:group-hover:bg-white/[0.06]"
            }`}
          />
          <span
            className={`relative z-10 block px-3.5 py-1 text-sm font-medium ${
              value === option.value ? "text-primary" : "text-foreground"
            }`}
          >
            {option.label}
          </span>
        </motion.button>
      ))}
    </div>
  );
}
