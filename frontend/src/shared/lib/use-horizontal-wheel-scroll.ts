import { useEffect, useRef } from "react";

/** A vertical mouse wheel does nothing on a horizontally-scrolling container by
 * default (only trackpad swipes / shift+wheel do) -- redirect wheel input to
 * horizontal scroll so a plain mouse wheel works too. React attaches onWheel as
 * a passive listener, so preventDefault() there is silently ignored and the page
 * scrolls too -- a plain addEventListener with `{ passive: false }` is required
 * to actually stop that. */
export function useHorizontalWheelScroll<T extends HTMLElement>() {
  const ref = useRef<T>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onWheel = (event: WheelEvent) => {
      if (el.scrollWidth <= el.clientWidth) return;
      event.preventDefault();
      el.scrollLeft += event.deltaY;
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  return ref;
}
