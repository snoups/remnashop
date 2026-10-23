import { CircleHelp } from "lucide-react";
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { HINT_BUBBLE_CLASS } from "@shared/ui/hint-bubble";

interface FieldHintProps {
  text: string;
  /** rich bubble body (swatches, lists) in place of `text` */
  content?: ReactNode;
  side?: "top" | "bottom";
  /** "end" lines the bubble's right edge up with the icon instead of centering it */
  align?: "center" | "end";
}

const GAP_PX = 8;
const VIEWPORT_MARGIN_PX = 8;

// Portalled to the body, so no scroll container or overflow-hidden panel clips the bubble.
// Focusable, so the bubble also opens on keyboard focus.
export function FieldHint({ text, content, side = "top", align = "center" }: FieldHintProps) {
  const iconRef = useRef<HTMLSpanElement>(null);
  const bubbleRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 0, top: 0 });

  useLayoutEffect(() => {
    const icon = iconRef.current?.getBoundingClientRect();
    const bubble = bubbleRef.current?.getBoundingClientRect();
    // closing keeps the last position, so the bubble fades out in place
    if (!open || !icon || !bubble) return;
    const preferred = align === "end" ? icon.right - bubble.width : icon.left + icon.width / 2 - bubble.width / 2;
    const maxLeft = window.innerWidth - bubble.width - VIEWPORT_MARGIN_PX;
    setPosition({
      left: Math.max(VIEWPORT_MARGIN_PX, Math.min(preferred, maxLeft)),
      top: side === "top" ? icon.top - bubble.height - GAP_PX : icon.bottom + GAP_PX,
    });
  }, [open, side, align]);

  // the bubble is fixed in place, so it would drift off the icon on scroll
  useLayoutEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("scroll", close, true);
    return () => window.removeEventListener("scroll", close, true);
  }, [open]);

  return (
    <span
      ref={iconRef}
      tabIndex={0}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      className="relative inline-flex rounded-full outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
    >
      <CircleHelp className="size-3.5 shrink-0 cursor-help text-muted-foreground" />
      {createPortal(
        // always mounted: a CSS opacity transition reverses smoothly when the pointer
        // flickers across the icon's edge, a mount/unmount animation restarts
        <span
          ref={bubbleRef}
          // above Modal (z-50) and PortalPopover (z-60)
          className={`${HINT_BUBBLE_CLASS} z-[70] whitespace-pre-line`}
          style={{ position: "fixed", ...position, opacity: open ? 1 : 0 }}
        >
          {content ?? text}
        </span>,
        document.body,
      )}
    </span>
  );
}
