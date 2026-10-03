import { useState } from "react";

/** Keys of the collapsed groups in a list; everything starts expanded. */
export function useCollapsedSet<K extends string = string>(): [ReadonlySet<K>, (key: K) => void] {
  const [collapsed, setCollapsed] = useState<ReadonlySet<K>>(new Set());
  const toggle = (key: K) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (!next.delete(key)) next.add(key);
      return next;
    });
  return [collapsed, toggle];
}
