import type { ComponentType, ReactNode } from "react";

/** 32px icon circle. header: a section or dialog title's, bordered; row: a settings row's, plain.
 *  glyph: the circle's content instead of an icon (an emoji, a logo). */
export function IconCircle({
  icon: Icon,
  glyph,
  header = false,
}: {
  icon?: ComponentType<{ className?: string }>;
  glyph?: ReactNode;
  header?: boolean;
}) {
  return (
    <div
      className={`flex shrink-0 items-center justify-center rounded-full text-foreground ${
        header ? "size-9 border border-glass-border bg-white/[0.05]" : "size-8 bg-white/[0.06]"
      }`}
    >
      {glyph ?? (Icon && <Icon className="size-4" />)}
    </div>
  );
}
