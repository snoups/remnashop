import { AnimatePresence, motion, type HTMLMotionProps } from "motion/react";
import { useLayoutEffect, useState, type RefObject } from "react";
import { createPortal } from "react-dom";

import {
  anchorFor,
  leftAnchorFor,
  rightAnchorFor,
  type LeftPopoverAnchor,
  type PopoverAnchor,
  type RightPopoverAnchor,
} from "@shared/lib/popover-anchor";
import { POPOVER_CLASS } from "@shared/ui/classes";

interface PortalPopoverProps extends Omit<HTMLMotionProps<"div">, "ref" | "className"> {
  open: boolean;
  triggerRef: RefObject<HTMLElement | null>;
  /** pass it to useClickOutside / useCloseOnScroll next to the trigger's ref */
  popoverRef: RefObject<HTMLDivElement | null>;
  /** the trigger edge the popover lines up with, keeping its own width; stretch: as wide as the trigger */
  align: "left" | "right" | "stretch";
  /** opens upward when this much room is missing below the trigger */
  maxHeight: number;
  /** size and padding only (w-80 p-1.5...) */
  className: string;
  /** no backdrop blur: for content that repaints every frame (animated emoji), which a blur re-renders */
  solid?: boolean;
  /** false: no click-catching layer under the open popover, for one that stays open while its trigger is used (a search
   * field) or opens on hover (the layer would take the pointer off the trigger and close it) */
  modal?: boolean;
}

const SOLID_POPOVER_CLASS =
  "rounded-popover border border-white/[0.14] bg-popover shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)]";

function anchorWith(align: PortalPopoverProps["align"], trigger: DOMRect, maxHeight: number) {
  if (align === "stretch") return anchorFor(trigger, maxHeight);
  return align === "right" ? rightAnchorFor(trigger, maxHeight) : leftAnchorFor(trigger, maxHeight);
}

// Portalled to the body: rendered in place, the dashboard panel's
// backdrop-filter becomes the popover's backdrop root, and its glass stops
// blurring anything behind the panel.
// measured on open only; useCloseOnScroll closes it when the trigger moves.
export function PortalPopover({
  open,
  triggerRef,
  popoverRef,
  align,
  maxHeight,
  className,
  solid = false,
  modal = true,
  style,
  children,
  ...motionProps
}: PortalPopoverProps) {
  const [anchor, setAnchor] = useState<PopoverAnchor | LeftPopoverAnchor | RightPopoverAnchor | null>(null);

  useLayoutEffect(() => {
    const trigger = open ? triggerRef.current?.getBoundingClientRect() : undefined;
    if (trigger) setAnchor(anchorWith(align, trigger, maxHeight));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- measured once per open
  }, [open]);

  return createPortal(
    <>
      {/* a click outside only closes the popover, nothing behind it reacts; same z, earlier in the DOM: under it */}
      {modal && open && <div className="fixed inset-0 z-[60]" />}
      <AnimatePresence>
        {open && anchor && (
          <motion.div
            ref={popoverRef}
            {...motionProps}
            style={{
              transformOrigin: `${"top" in anchor ? "top" : "bottom"} ${align === "stretch" ? "center" : align}`,
              ...anchor,
              ...style,
            }}
            // above Modal's z-50, so a popover opened inside a dialog draws over it
            className={`${solid ? SOLID_POPOVER_CLASS : POPOVER_CLASS} fixed z-[60] ${className}`}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </>,
    document.body,
  );
}
