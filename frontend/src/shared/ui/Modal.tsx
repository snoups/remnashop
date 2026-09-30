import { AnimatePresence, motion } from "motion/react";
import {
  type ReactNode,
  type RefObject,
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { createPortal } from "react-dom";

import { DialogPortal } from "@shared/ui/DialogPortal";
import { ModalCloseContext, useDialogFocus } from "@shared/ui/modal-hooks";

const SIZE_CLASS = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-3xl",
} as const;

// the enclosing modal's panel, if any: a nested modal renders into its backdrop and morphs
// out of it, instead of stacking a second backdrop (which would also re-root backdrop-blur
// and make the nested panel read lighter than its parent)
const ParentPanelContext = createContext<RefObject<HTMLDivElement | null> | null>(null);
const INSTANT = { duration: 0 };
const MORPH_OPTIONS: KeyframeAnimationOptions = { duration: 200, easing: "ease-out", fill: "forwards" };
const PANEL_CLIP_RADIUS = "round var(--radius-dialog)";

// The parent panel becomes a content-less "ghost" resizing between the two boxes while the
// nested panel's content is clipped to it -- one box morphing, like the tab height animation.
async function morphPanels(parent: HTMLElement, child: HTMLElement, direction: "in" | "out"): Promise<void> {
  const from = parent.getBoundingClientRect();
  const to = child.getBoundingClientRect();
  const parentClip = `inset(${[from.top - to.top, to.right - from.right, to.bottom - from.bottom, from.left - to.left]
    .map((value) => `${Math.max(0, value)}px`)
    .join(" ")} ${PANEL_CLIP_RADIUS})`;
  const boxes = [
    { width: `${from.width}px`, height: `${from.height}px` },
    { width: `${to.width}px`, height: `${to.height}px` },
  ];
  const clips = [{ clipPath: parentClip }, { clipPath: `inset(0 ${PANEL_CLIP_RADIUS})` }];
  if (direction === "out") {
    boxes.reverse();
    clips.reverse();
  }

  parent.style.visibility = "";
  parent.dataset.morphGhost = "";
  child.dataset.morphing = "";
  const animations = [parent.animate(boxes, MORPH_OPTIONS), child.animate(clips, MORPH_OPTIONS)];
  await Promise.all(animations.map((animation) => animation.finished)).catch(() => {});

  // swap before dropping the held last frame, so neither box flashes at its own size
  if (direction === "in") parent.style.visibility = "hidden";
  else child.style.visibility = "hidden";
  delete parent.dataset.morphGhost;
  delete child.dataset.morphing;
  animations.forEach((animation) => animation.cancel());
}

interface ModalProps {
  /** Fires after the exit animation finishes -- unmount the modal here. */
  onClose: () => void;
  size?: keyof typeof SIZE_CLASS;
  /** Panel becomes a flex column capped at 85vh; children own their scroll region. */
  scrollable?: boolean;
  /** false: backdrop click and Esc don't dismiss (the modal must be acknowledged). */
  dismissable?: boolean;
  /** false: render in place instead of portaling -- for a caller that deliberately wants
   * the backdrop bounded by its own container. Off by default; see DialogPortal's own
   * comment for why portaling is almost always the right call. */
  portal?: boolean;
  children: ReactNode;
}

export function Modal({
  onClose,
  size = "sm",
  scrollable = false,
  dismissable = true,
  portal = true,
  children,
}: ModalProps) {
  const [open, setOpen] = useState(true);
  const parentPanelRef = useContext(ParentPanelContext);
  const isNested = parentPanelRef !== null;
  const panelRef = useRef<HTMLDivElement>(null);
  const isClosingRef = useRef(false);

  const requestClose = useCallback(() => {
    const parentPanel = parentPanelRef?.current;
    const panel = panelRef.current;
    if (!parentPanel || !panel) {
      setOpen(false);
      return;
    }
    if (isClosingRef.current) return;
    isClosingRef.current = true;
    void morphPanels(parentPanel, panel, "out").then(() => setOpen(false));
  }, [parentPanelRef]);

  // Parent shown/hidden via the DOM, not state: it has to be visible again before focus
  // returns into it on unmount. Layout effect so the first paint is already the morph's start.
  useLayoutEffect(() => {
    const parentPanel = parentPanelRef?.current;
    const panel = panelRef.current;
    if (!parentPanel || !panel) return;
    void morphPanels(parentPanel, panel, "in");
    return () => {
      parentPanel.style.visibility = "";
      delete parentPanel.dataset.morphGhost;
    };
  }, [parentPanelRef]);

  useDialogFocus(panelRef, dismissable ? requestClose : null);

  const content = (
    <ParentPanelContext.Provider value={panelRef}>
    <ModalCloseContext.Provider value={requestClose}>
      <AnimatePresence onExitComplete={onClose}>
        {open && (
          <motion.div
            initial={isNested ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={isNested ? INSTANT : { duration: 0.15, ease: "easeOut" }}
            className={
              isNested
                ? "absolute inset-0 z-50 flex items-center justify-center p-4"
                : "fixed inset-0 z-40 flex items-center justify-center bg-black/55 p-4 backdrop-blur-3xl"
            }
          >
            {dismissable && (
              <button
                type="button"
                aria-hidden
                tabIndex={-1}
                className="absolute inset-0 cursor-default"
                onClick={requestClose}
              />
            )}

            <motion.div
              ref={panelRef}
              role="dialog"
              aria-modal
              tabIndex={-1}
              initial={isNested ? false : { opacity: 0, scale: 0.94, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 8 }}
              transition={isNested ? INSTANT : { duration: 0.18, ease: "easeOut" }}
              className={`relative z-50 w-full ${SIZE_CLASS[size]} rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] outline-none backdrop-blur-2xl backdrop-saturate-150 ${
                scrollable ? "flex max-h-[85vh] flex-col" : ""
              }`}
            >
              {children}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </ModalCloseContext.Provider>
    </ParentPanelContext.Provider>
  );

  // nested: into the parent's backdrop, sharing its dimming and its backdrop-blur root
  const parentBackdrop = parentPanelRef?.current?.parentElement;
  if (parentBackdrop) return createPortal(content, parentBackdrop);
  return portal ? <DialogPortal>{content}</DialogPortal> : content;
}
