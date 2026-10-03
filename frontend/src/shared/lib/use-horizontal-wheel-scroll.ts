import { useCallback, useEffect, useRef } from "react";

/** Lets a plain mouse wheel scroll a horizontal strip (by default only
 * trackpads and shift+wheel do). React's onWheel is passive and ignores
 * preventDefault(), hence addEventListener with `{ passive: false }`.
 *
 * A callback ref: the strip may mount long after the hook (the emoji picker's
 * tabs exist only while its popover is open). */
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
