import type { HTMLAttributes } from "react";

export type BadgeTone = "success" | "warning" | "error" | "neutral" | "accent" | "violet";

const TONE_CLASS: Record<BadgeTone, string> = {
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  error: "bg-error/10 text-error",
  neutral: "bg-white/[0.04] text-muted-foreground",
  accent: "bg-accent text-primary",
  violet: "bg-violet-400/10 text-violet-300",
};

const SHAPE_CLASS = {
  pill: "gap-1 px-2 py-0.5 text-xs uppercase tracking-wide",
  // a circle for one digit, stretching into a pill for more
  count: "h-6 min-w-6 justify-center px-1.5 text-xs tabular-nums",
} as const;

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  shape?: keyof typeof SHAPE_CLASS;
}

/** Status pill: uppercase, tinted by tone; shape="count" for a number. */
export function Badge({ tone = "neutral", shape = "pill", className = "", ...props }: BadgeProps) {
  return (
    <span
      className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full font-semibold ${SHAPE_CLASS[shape]} ${TONE_CLASS[tone]} ${className}`}
      {...props}
    />
  );
}
