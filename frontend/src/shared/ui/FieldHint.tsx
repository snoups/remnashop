import { CircleHelp } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { ERROR_HINT_BUBBLE_CLASS, HINT_BUBBLE_CLASS } from "@shared/ui/hint-bubble";

interface FieldHintProps {
  text: string;
  /** rich bubble body (swatches, lists) in place of `text` */
  content?: ReactNode;
  side?: "top" | "bottom";
  /** "end" lines the bubble's right edge up with the icon instead of centering it */
  align?: "center" | "end";
  /** an error's text: the bubble, red */
  error?: boolean;
  /** what the bubble hangs off, in place of the ? icon (a status badge) */
  trigger?: ReactNode;
  /** layout of the trigger wrapper */
  className?: string;
}

const GAP_PX = 8;
const EDGE_MARGIN_PX = 8;
const CLOSE_DELAY_MS = 150;

// the trigger's dialog, else the dashboard's panel (DashboardLayout), else the viewport: a bubble stays inside it
function boundsRect(anchor?: HTMLElement): { left: number; top: number; right: number; bottom: number } {
  const dialog = anchor?.closest<HTMLElement>("[data-dialog]")?.getBoundingClientRect();
  if (dialog && dialog.width > 0) return dialog;
  const panel = document.querySelector("[data-dashboard-panel]")?.getBoundingClientRect();
  if (panel && panel.width > 0) return panel;
  return { left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight };
}

// Portalled to the body, so no scroll container or overflow-hidden panel clips the bubble.
// Focusable, so the bubble also opens on keyboard focus.
export function FieldHint({ text, content, side = "top", align = "center", error = false, trigger, className = "" }: FieldHintProps) {
  const iconRef = useRef<HTMLSpanElement>(null);
  const bubbleRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 0, top: 0 });
  const closeTimer = useRef<number | undefined>(undefined);
  // a tap toggles, a mouse hovers: the pointer that pressed decides what the click means
  const lastPointer = useRef("mouse");

  const show = () => {
    window.clearTimeout(closeTimer.current);
    setOpen(true);
  };
  // a moment's grace to cross the gap onto the bubble and select its text
  const hideSoon = () => {
    window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpen(false), CLOSE_DELAY_MS);
  };
  useEffect(() => () => window.clearTimeout(closeTimer.current), []);

  // a tap outside the icon and the bubble closes a tapped-open hint
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (iconRef.current?.contains(target) || bubbleRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  useLayoutEffect(() => {
    const icon = iconRef.current?.getBoundingClientRect();
    const bubble = bubbleRef.current?.getBoundingClientRect();
    // closing keeps the last position, so the bubble fades out in place
    if (!open || !icon || !bubble) return;
    const bounds = boundsRect(iconRef.current ?? undefined);
    const preferred = align === "end" ? icon.right - bubble.width : icon.left + icon.width / 2 - bubble.width / 2;
    const minLeft = bounds.left + EDGE_MARGIN_PX;
    const maxLeft = bounds.right - bubble.width - EDGE_MARGIN_PX;
    const above = icon.top - bubble.height - GAP_PX;
    const below = icon.bottom + GAP_PX;
    // the preferred side, flipped when the bubble would cross the panel's edge there
    const fitsAbove = above >= bounds.top + EDGE_MARGIN_PX;
    const fitsBelow = below + bubble.height <= bounds.bottom - EDGE_MARGIN_PX;
    const top = side === "top" ? (fitsAbove || !fitsBelow ? above : below) : fitsBelow || !fitsAbove ? below : above;
    setPosition({ left: Math.max(minLeft, Math.min(preferred, maxLeft)), top });
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
      onPointerDown={(event) => (lastPointer.current = event.pointerType)}
      onPointerEnter={(event) => event.pointerType === "mouse" && show()}
      onPointerLeave={(event) => event.pointerType === "mouse" && hideSoon()}
      onClick={(event) => {
        // the hint sits in clickable rows and labels; the bubble's clicks reach here through the portal
        event.stopPropagation();
        event.preventDefault();
        if (!iconRef.current?.contains(event.target as Node)) return;
        if (lastPointer.current !== "mouse") setOpen((value) => !value);
      }}
      // keyboard focus only: a tap focuses too, and would reopen what the tap just toggled
      onFocus={(event) => event.currentTarget.matches(":focus-visible") && show()}
      onBlur={(event) => {
        if (!bubbleRef.current?.contains(event.relatedTarget as Node | null)) setOpen(false);
      }}
      className={`relative inline-flex rounded-full outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-primary ${className}`}
    >
      {trigger ?? (
        <CircleHelp
          className="size-3.5 shrink-0 cursor-help text-muted-foreground transition-colors hover:text-foreground"
        />
      )}
      {createPortal(
        // always mounted: a CSS opacity transition reverses smoothly when the pointer
        // flickers across the icon's edge, a mount/unmount animation restarts
        <span
          ref={bubbleRef}
          // above everything: Modal (z-50), PortalPopover (z-60), toasts and the debug bar (z-50)
          className={`${error ? ERROR_HINT_BUBBLE_CLASS : HINT_BUBBLE_CLASS} z-[100] cursor-text select-text whitespace-pre-line`}
          // open, it takes the pointer: hovering it keeps it, its text can be selected
          style={{ position: "fixed", ...position, opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none" }}
          onPointerEnter={(event) => event.pointerType === "mouse" && show()}
          onPointerLeave={(event) => event.pointerType === "mouse" && hideSoon()}
        >
          {content ?? text}
        </span>,
        document.body,
      )}
    </span>
  );
}
