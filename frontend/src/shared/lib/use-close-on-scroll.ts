import { useEffect, type RefObject } from "react";

/** Closes a popover when the page (or a panel under it) scrolls away from its
 * trigger. `inside` is the popover's own box: scrolling its list must not
 * close it; pass an array when there is more than one popover. */
export function useCloseOnScroll<T extends Element>(
  active: boolean,
  inside: RefObject<T | null> | RefObject<T | null>[],
  onClose: () => void,
) {
  useEffect(() => {
    if (!active) return;

    const refList = Array.isArray(inside) ? inside : [inside];
    // capture: scroll doesn't bubble, and what moves is usually an inner panel
    const handleScroll = (event: Event) => {
      const target = event.target as Node;
      if (refList.some((ref) => ref.current?.contains(target))) return;
      onClose();
    };
    const handleResize = () => onClose();

    window.addEventListener("scroll", handleScroll, true);
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("scroll", handleScroll, true);
      window.removeEventListener("resize", handleResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- inside/onClose are stable across renders
  }, [active]);
}
