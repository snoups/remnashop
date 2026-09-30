const POPOVER_GAP = 8;

type VerticalAnchor = { top: number } | { bottom: number };

export type PopoverAnchor = { left: number; width: number } & VerticalAnchor;
export type RightPopoverAnchor = { right: number } & VerticalAnchor;
export type LeftPopoverAnchor = { left: number } & VerticalAnchor;

/** Below the trigger, or above it when there's no room for `maxHeight` underneath. */
function verticalFor(trigger: DOMRect, maxHeight: number): VerticalAnchor {
  return window.innerHeight - trigger.bottom < maxHeight && trigger.top > maxHeight
    ? { bottom: window.innerHeight - trigger.top + POPOVER_GAP }
    : { top: trigger.bottom + POPOVER_GAP };
}

/** Fixed-position box for a body-portalled popover, as wide as its trigger. */
export function anchorFor(trigger: DOMRect, maxHeight: number): PopoverAnchor {
  return { left: trigger.left, width: trigger.width, ...verticalFor(trigger, maxHeight) };
}

/** Same, for an icon-sized trigger: the popover keeps its own width and lines
 * up with the trigger's right edge. */
export function rightAnchorFor(trigger: DOMRect, maxHeight: number): RightPopoverAnchor {
  return { right: window.innerWidth - trigger.right, ...verticalFor(trigger, maxHeight) };
}

/** Same, lined up with the trigger's left edge; the popover keeps its own width. */
export function leftAnchorFor(trigger: DOMRect, maxHeight: number): LeftPopoverAnchor {
  return { left: trigger.left, ...verticalFor(trigger, maxHeight) };
}
