import type { HTMLAttributes } from "react";

export type BadgeTone = "success" | "warning" | "error" | "neutral" | "accent" | "violet";

const TONE_CLASS: Record<BadgeTone, string> = {
  success: "border-success/30 bg-success/10 text-success",
  warning: "border-warning/30 bg-warning/10 text-warning",
  error: "border-error/30 bg-error/10 text-error",
  neutral: "border-border bg-white/[0.04] text-muted-foreground",
  accent: "border-primary/40 bg-accent text-primary",
  violet: "border-violet-400/35 bg-violet-400/10 text-violet-300",
};

const SHAPE_CLASS = {
  pill: "gap-1 px-2 py-0.5 text-[11px] uppercase tracking-wide",
  // a circle for one digit, stretching into a pill for more
  count: "h-6 min-w-6 justify-center px-1.5 text-[11px] tabular-nums",
} as const;

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  shape?: keyof typeof SHAPE_CLASS;
  /** no edge: the tone's tint alone */
  borderless?: boolean;
}

/** Status pill: uppercase, bordered, colored by tone; shape="count" for a number. */
export function Badge({ tone = "neutral", shape = "pill", borderless = false, className = "", ...props }: BadgeProps) {
  return (
    <span
      className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full ${borderless ? "" : "border"} font-semibold ${SHAPE_CLASS[shape]} ${TONE_CLASS[tone]} ${className}`}
      {...props}
    />
  );
}
