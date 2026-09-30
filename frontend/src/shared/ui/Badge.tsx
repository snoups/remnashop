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

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

/** Status pill: uppercase, bordered, colored by tone. */
export function Badge({ tone = "neutral", className = "", ...props }: BadgeProps) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${TONE_CLASS[tone]} ${className}`}
      {...props}
    />
  );
}
