import { useCallback, useEffect, useRef } from "react";

/** A vertical mouse wheel does nothing on a horizontally-scrolling container by
 * default (only trackpad swipes / shift+wheel do) -- redirect wheel input to
 * horizontal scroll so a plain mouse wheel works too. React attaches onWheel as
 * a passive listener, so preventDefault() there is silently ignored and the page
 * scrolls too -- a plain addEventListener with `{ passive: false }` is required
 * to actually stop that.
 *
 * A callback ref, not an object one: the strip may mount long after the hook
 * does (the emoji picker's tabs only exist while its popover is open), and an
 * effect that read `.current` on mount would find nothing there. */
export function useHorizontalWheelScroll<T extends HTMLElement>() {
  const detach = useRef<(() => void) | null>(null);

  useEffect(() => () => detach.current?.(), []);

  return useCallback((el: T | null) => {
    detach.current?.();
    detach.current = null;
    if (!el) return;

    const onWheel = (event: WheelEvent) => {
      if (el.scrollWidth <= el.clientWidth) return;
      event.preventDefault();
      el.scrollLeft += event.deltaY;
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    detach.current = () => el.removeEventListener("wheel", onWheel);
  }, []);
}
