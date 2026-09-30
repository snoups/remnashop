import { AnimatePresence, motion, type HTMLMotionProps } from "motion/react";
import { useLayoutEffect, useState, type RefObject } from "react";
import { createPortal } from "react-dom";

import {
  leftAnchorFor,
  rightAnchorFor,
  type LeftPopoverAnchor,
  type RightPopoverAnchor,
} from "@shared/lib/popover-anchor";
import { POPOVER_CLASS } from "@shared/ui/classes";

interface PortalPopoverProps extends Omit<HTMLMotionProps<"div">, "ref" | "className"> {
  open: boolean;
  triggerRef: RefObject<HTMLElement | null>;
  /** pass it to useClickOutside / useCloseOnScroll next to the trigger's ref */
  popoverRef: RefObject<HTMLDivElement | null>;
  /** the trigger edge the popover lines up with; it keeps its own width */
  align: "left" | "right";
  /** opens upward when this much room is missing below the trigger */
  maxHeight: number;
  /** size and padding only (w-80 p-1.5...) */
  className: string;
}

// Portalled to the body: rendered in place, the dashboard panel's own
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
  style,
  children,
  ...motionProps
}: PortalPopoverProps) {
  const [anchor, setAnchor] = useState<LeftPopoverAnchor | RightPopoverAnchor | null>(null);

  useLayoutEffect(() => {
    const trigger = open ? triggerRef.current?.getBoundingClientRect() : undefined;
    if (trigger) setAnchor(align === "right" ? rightAnchorFor(trigger, maxHeight) : leftAnchorFor(trigger, maxHeight));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- measured once per open
  }, [open]);

  return createPortal(
    <AnimatePresence>
      {open && anchor && (
        <motion.div
          ref={popoverRef}
          {...motionProps}
          style={{ transformOrigin: `${"top" in anchor ? "top" : "bottom"} ${align}`, ...anchor, ...style }}
          // above Modal's z-50, like SelectDropdown
          className={`${POPOVER_CLASS} fixed z-[60] ${className}`}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
