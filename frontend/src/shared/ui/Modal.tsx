import { AnimatePresence, motion } from "motion/react";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { DialogPortal } from "@shared/ui/DialogPortal";

const SIZE_CLASS = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
} as const;

const FOCUSABLE_SELECTOR =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

const ModalCloseContext = createContext<() => void>(() => {});

/** Runs the modal's exit animation, then its `onClose`. Call from anywhere inside a `<Modal>`. */
export function useModalClose(): () => void {
  return useContext(ModalCloseContext);
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
  const panelRef = useRef<HTMLDivElement>(null);
  const requestClose = useCallback(() => setOpen(false), []);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && dismissable) {
        event.stopPropagation();
        requestClose();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusables = [...panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)];
      if (focusables.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      previouslyFocused?.focus?.();
    };
  }, [dismissable, requestClose]);

  const content = (
    <ModalCloseContext.Provider value={requestClose}>
      <AnimatePresence onExitComplete={onClose}>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
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
              initial={{ opacity: 0, scale: 0.94, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 8 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
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
  );

  return portal ? <DialogPortal>{content}</DialogPortal> : content;
}
