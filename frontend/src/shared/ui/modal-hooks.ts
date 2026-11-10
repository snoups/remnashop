import { type RefObject, createContext, useContext, useEffect, useRef } from "react";

const FOCUSABLE_SELECTOR =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

// open panels, innermost last; only it handles Esc/Tab when dialogs stack
const openPanels: HTMLDivElement[] = [];

export const ModalCloseContext = createContext<() => void>(() => {});

// the enclosing modal's panel, if any: a nested modal renders into its backdrop and morphs
// out of it, instead of stacking a second backdrop (which would also re-root backdrop-blur
// and make the nested panel read lighter than its parent). Exported so a dialog opened through
// the entity dialog host still nests in the dialog it was opened from.
export const ParentPanelContext = createContext<RefObject<HTMLDivElement | null> | null>(null);

/** Runs the modal's exit animation, then its `onClose`. Call from anywhere inside a `<Modal>`. */
export function useModalClose(): () => void {
  return useContext(ModalCloseContext);
}

/** Focus into the panel on open and back on close, Tab kept inside, Esc -> onEscape (null: Esc does nothing).
 * Exported for the build-info overlay, which keeps its own markup (see BuildInfoBadge). */
export function useDialogFocus(panelRef: RefObject<HTMLDivElement | null>, onEscape: (() => void) | null) {
  // a ref, so a new handler identity each render doesn't re-run the effect (and refocus the panel)
  const onEscapeRef = useRef(onEscape);
  onEscapeRef.current = onEscape;

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    panel?.focus();
    if (panel) openPanels.push(panel);

    const onKeyDown = (event: KeyboardEvent) => {
      if (openPanels[openPanels.length - 1] !== panel) return;
      if (event.key === "Escape" && onEscapeRef.current) {
        event.stopPropagation();
        onEscapeRef.current();
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
      if (panel) openPanels.splice(openPanels.indexOf(panel), 1);
      previouslyFocused?.focus?.();
    };
  }, [panelRef]);
}

/** The desktop backdrop covers only the dashboard panel (its backdrop-blur bounds `fixed`), so a press on
 *  the sidebar or the page margins dismisses the topmost dialog too, and only that: nothing under it reacts.
 *  Portaled popovers and toasts sit outside the shell and are left alone. */
export function useOutsidePanelDismiss(panelRef: RefObject<HTMLDivElement | null>, onDismiss: (() => void) | null) {
  const onDismissRef = useRef(onDismiss);
  onDismissRef.current = onDismiss;

  useEffect(() => {
    const isOutside = (event: Event) => {
      const panel = panelRef.current;
      if (!onDismissRef.current || !panel || openPanels[openPanels.length - 1] !== panel) return false;
      const target = event.target;
      const shell = document.querySelector("[data-dashboard-shell]");
      if (!(target instanceof Element) || !shell || target.closest("[data-dashboard-panel]")) return false;
      return target.closest("[data-dashboard-shell]") !== null || target.contains(shell);
    };
    const onPointerDown = (event: PointerEvent) => {
      if (isOutside(event)) event.stopPropagation();
    };
    const onClick = (event: MouseEvent) => {
      if (!isOutside(event)) return;
      event.preventDefault();
      event.stopPropagation();
      onDismissRef.current?.();
    };
    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("click", onClick, true);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("click", onClick, true);
    };
  }, [panelRef]);
}
