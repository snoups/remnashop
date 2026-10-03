import { useEffect, type RefObject } from "react";

/** Closes a popover/dropdown on a mousedown outside every given ref. Pass an
 * array when the trigger spans more than one element (e.g. two independent
 * popovers that must not close each other). */
export function useClickOutside<T extends Element>(
  refs: RefObject<T | null> | RefObject<T | null>[],
  active: boolean,
  onOutside: () => void,
) {
  useEffect(() => {
    if (!active) return;

    const refList = Array.isArray(refs) ? refs : [refs];
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (refList.every((ref) => !ref.current?.contains(target))) onOutside();
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refs/onOutside are stable (ref objects, setState setters)
  }, [active]);
}
