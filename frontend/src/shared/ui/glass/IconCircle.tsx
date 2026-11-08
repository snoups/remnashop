import type { ComponentType, ReactNode } from "react";

import type { BadgeTone } from "@shared/ui/Badge";

// a row circle in the status badge's tones
const TONE_CLASS: Record<BadgeTone, string> = {
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  error: "bg-error/10 text-error",
  neutral: "bg-white/[0.06] text-muted-foreground",
  accent: "bg-primary/10 text-primary",
  violet: "bg-violet-400/10 text-violet-300",
};

// a section or dialog title's circle: 36px, bordered
const HEADER_CLASS = {
  default: "border-glass-border bg-white/[0.05] text-foreground",
  danger: "border-error/30 bg-error/10 text-error",
  warning: "border-warning/30 bg-warning/15 text-warning",
} as const;

/** 32px icon circle. header: a section or dialog title's, bordered; row: a settings row's, plain.
 *  glyph: the circle's content instead of an icon (an emoji, a logo). */
export function IconCircle({
  icon: Icon,
  glyph,
  header = false,
  danger = false,
  warning = false,
  tone,
}: {
  icon?: ComponentType<{ className?: string }>;
  glyph?: ReactNode;
  header?: boolean;
  /** a destructive dialog's title */
  danger?: boolean;
  /** a critical announcement's title */
  warning?: boolean;
  /** a row circle colored by status */
  tone?: BadgeTone;
}) {
  const headerTone = danger ? "danger" : warning ? "warning" : header ? "default" : null;
  return (
    <span
      className={`flex shrink-0 items-center justify-center rounded-full ${
        headerTone
          ? `size-9 border ${HEADER_CLASS[headerTone]}`
          : `size-8 ${tone ? TONE_CLASS[tone] : "bg-white/[0.06] text-foreground"}`
      }`}
    >
      {glyph ?? (Icon && <Icon className="size-4" />)}
    </span>
  );
}
