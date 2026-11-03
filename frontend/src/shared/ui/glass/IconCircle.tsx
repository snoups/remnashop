import type { ComponentType, ReactNode } from "react";

/** 32px icon circle. header: a section or dialog title's, bordered; row: a settings row's, plain.
 *  glyph: the circle's content instead of an icon (an emoji, a logo). */
export function IconCircle({
  icon: Icon,
  glyph,
  header = false,
  danger = false,
  warning = false,
}: {
  icon?: ComponentType<{ className?: string }>;
  glyph?: ReactNode;
  header?: boolean;
  /** a destructive dialog's title */
  danger?: boolean;
  /** a critical announcement's title */
  warning?: boolean;
}) {
  return (
    <div
      className={`flex shrink-0 items-center justify-center rounded-full ${
        danger
          ? "size-9 border border-error/30 bg-error/10 text-error"
          : warning
            ? "size-9 border border-warning/30 bg-warning/15 text-warning"
            : header
            ? "size-9 border border-glass-border bg-white/[0.05] text-foreground"
            : "size-8 bg-white/[0.06] text-foreground"
      }`}
    >
      {glyph ?? (Icon && <Icon className="size-4" />)}
    </div>
  );
}
