import { AnimatePresence, motion } from "motion/react";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

const GAP = 12;
const WIDTH = 256;
const MAX_HEIGHT = 480;

interface AnchoredPopoverProps {
  /** The canvas element the popover is positioned next to. `null` keeps it unmounted. */
  anchorEl: HTMLElement | null;
  onClose: () => void;
  children: ReactNode;
}

/** Floats `children` in a fixed-position panel next to `anchorEl`, flipping to the
 * left when it would overflow the right edge of the viewport. Portals to
 * `document.body` -- `main`'s `mask-image` is a containing block for
 * `position: fixed` descendants, so viewport coordinates only hold outside it
 * (see DialogPortal). Repositions on resize/scroll, closes on outside click or
 * Escape. Only ever rendered on viewports at or above the `lg` breakpoint --
 * narrower viewports render the same content through `Modal` instead (see
 * DialogCanvasEditor). */
export function AnchoredPopover({ anchorEl, onClose, children }: AnchoredPopoverProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  useLayoutEffect(() => {
    if (!anchorEl) {
      setPosition(null);
      return;
    }
    const compute = () => {
      const rect = anchorEl.getBoundingClientRect();
      const overflowsRight = rect.right + GAP + WIDTH > window.innerWidth;
      const left = overflowsRight ? Math.max(GAP, rect.left - GAP - WIDTH) : rect.right + GAP;
      const panelHeight = panelRef.current?.offsetHeight ?? MAX_HEIGHT;
      const top = Math.min(Math.max(rect.top, GAP), Math.max(GAP, window.innerHeight - GAP - panelHeight));
      setPosition({ top, left });
    };
    compute();
    // first pass runs before the panel exists, so its height is a guess -- redo it once measured
    const frame = requestAnimationFrame(compute);
    window.addEventListener("resize", compute);
    window.addEventListener("scroll", compute, true);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", compute);
      window.removeEventListener("scroll", compute, true);
    };
  }, [anchorEl]);

  useEffect(() => {
    if (!anchorEl) return;
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      // switching directly from one open selection to another briefly
      // unmounts the popover (mousedown-close fires before the new click-select) --
      // cosmetic at most, revisit only if it visibly flickers in practice.
      if (panelRef.current?.contains(target) || anchorEl.contains(target)) return;
      // a dialog opened from inside the popover portals to #dialog-root, outside panelRef
      if (target instanceof Element && target.closest("#dialog-root")) return;
      onClose();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [anchorEl, onClose]);

  return createPortal(
    <AnimatePresence>
      {anchorEl && position && (
        <motion.div
          ref={panelRef}
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.96 }}
          transition={{ duration: 0.15, ease: "easeOut" }}
          style={{ position: "fixed", top: position.top, left: position.left, width: WIDTH }}
          className="z-30 max-h-[min(480px,calc(100vh-24px))] overflow-y-auto"
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
