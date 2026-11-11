import { AnimatePresence, motion, type HTMLMotionProps } from "motion/react";
import { useLayoutEffect, useState, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";

import {
  anchorFor,
  leftAnchorFor,
  rightAnchorFor,
  type LeftPopoverAnchor,
  type PopoverAnchor,
  type RightPopoverAnchor,
} from "@shared/lib/popover-anchor";
import { GLASS_POPOVER_CLASS, POPOVER_CLASS, POPOVER_EDGE_CLASS } from "@shared/ui/classes";
import { FieldRequiredContext } from "@shared/ui/field-context";

interface PortalPopoverProps extends Omit<HTMLMotionProps<"div">, "ref" | "className" | "children"> {
  children?: ReactNode;
  open: boolean;
  triggerRef: RefObject<HTMLElement | null>;
  /** pass it to useClickOutside / useCloseOnScroll next to the trigger's ref */
  popoverRef: RefObject<HTMLDivElement | null>;
  /** the trigger edge the popover lines up with, keeping its own width; stretch: as wide as the trigger */
  align: "left" | "right" | "stretch";
  /** opens upward when this much room is missing below the trigger */
  maxHeight: number;
  /** Extra space beyond the standard 8px gap from the trigger. */
  extraGap?: number;
  /** size and padding only (w-80 p-1.5...) */
  className: string;
  /** no backdrop blur: for content that repaints every frame (animated emoji), which a blur re-renders */
  solid?: boolean;
  /** the glass design's material (the header's capsule menus) */
  glass?: boolean;
  /** false: no click-catching layer under the open popover, for one that stays open while its trigger is used (a search
   * field) or opens on hover (the layer would take the pointer off the trigger and close it) */
  modal?: boolean;
}

// glass-dialog's edge and shadow on an opaque fill, no blur
const SOLID_GLASS_POPOVER_CLASS =
  "rounded-popover bg-popover shadow-[inset_0_1px_0_rgb(255_255_255/0.2),inset_0_0_0_1px_rgb(255_255_255/0.12),0_0_0_1px_rgb(0_0_0/0.35),0_40px_80px_-24px_rgb(0_0_0/0.7)]";
const SOLID_POPOVER_CLASS = `${POPOVER_EDGE_CLASS} bg-popover`;

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
  extraGap = 0,
  className,
  solid = false,
  glass = false,
  modal = true,
  style,
  children,
  ...motionProps
}: PortalPopoverProps) {
  const [anchor, setAnchor] = useState<PopoverAnchor | LeftPopoverAnchor | RightPopoverAnchor | null>(null);

  useLayoutEffect(() => {
    const trigger = open ? triggerRef.current?.getBoundingClientRect() : undefined;
    if (trigger) {
      const next = anchorWith(align, trigger, maxHeight + extraGap);
      setAnchor("top" in next ? { ...next, top: next.top + extraGap } : { ...next, bottom: next.bottom + extraGap });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- measured once per open
  }, [open]);

  return createPortal(
    <>
      {/* a click outside only closes the popover, nothing behind it reacts; same z, earlier in the DOM: under it */}
      {modal && open && <div className="fixed inset-0 z-60" />}
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
            className={`${solid ? (glass ? SOLID_GLASS_POPOVER_CLASS : SOLID_POPOVER_CLASS) : glass ? GLASS_POPOVER_CLASS : POPOVER_CLASS} fixed z-60 ${className}`}
          >
            {/* a popover opened from a required Field has fields of its own */}
            <FieldRequiredContext.Provider value={false}>{children}</FieldRequiredContext.Provider>
          </motion.div>
        )}
      </AnimatePresence>
    </>,
    document.body,
  );
}
