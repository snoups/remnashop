import { useEffect, useRef, useState, type RefObject } from "react";

// ResizeObserver-driven so a dialog also eases when a tab's own content changes (sessions loading in)
export function useMeasuredHeight(): [RefObject<HTMLDivElement | null>, number | "auto"] {
  const ref = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number | "auto">("auto");

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setHeight(entry.contentRect.height));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return [ref, height];
}
