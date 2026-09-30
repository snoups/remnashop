import { CircleHelp } from "lucide-react";
import type { ReactNode } from "react";

import { HINT_BUBBLE_CLASS } from "@shared/ui/hint-bubble";

interface FieldHintProps {
  text: string;
  /** rich bubble body (swatches, lists); `text` stays the accessible name */
  content?: ReactNode;
  side?: "top" | "bottom";
  /** "end" keeps the bubble inside the panel when the icon sits at its right
   * edge -- centered, it would be clipped by the scroll container. */
  align?: "center" | "end";
}

// Focusable so keyboard users reach it too; the hint itself is the accessible
// name, so the bubble stays hidden from screen readers to avoid a double read.
export function FieldHint({ text, content, side = "top", align = "center" }: FieldHintProps) {
  return (
    <span tabIndex={0} role="img" aria-label={text} className="group relative inline-flex rounded-full outline-none focus-visible:ring-2 focus-visible:ring-primary/60">
      <CircleHelp className="size-3.5 shrink-0 cursor-help text-muted-foreground" aria-hidden="true" />
      <span
        aria-hidden
        className={`${HINT_BUBBLE_CLASS} z-20 whitespace-pre-line group-hover:opacity-100 group-focus-visible:opacity-100 ${
          side === "top" ? "bottom-full mb-2" : "top-full mt-2"
        } ${align === "end" ? "right-0" : "left-1/2 -translate-x-1/2"}`}
      >
        {content ?? text}
      </span>
    </span>
  );
}
