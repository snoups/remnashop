import { useEffect, useRef } from "react";

import { useHorizontalWheelScroll } from "@shared/lib/use-horizontal-wheel-scroll";

interface PillTabsProps<T extends string> {
  items: { key: T; label: string }[];
  activeKey: T | null;
  onSelect: (key: T) => void;
}

/** Tabs share the width when they fit and scroll sideways when they don't --
 * the locale row grows with every language a shop turns on. */
export function PillTabs<T extends string>({ items, activeKey, onSelect }: PillTabsProps<T>) {
  const scrollerRef = useHorizontalWheelScroll<HTMLDivElement>();
  const activeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    // With twenty locales the selected one can sit past the right edge, and a
    // tab you cannot see reads as no selection at all.
    activeRef.current?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [activeKey]);

  return (
    <div className="flex w-full rounded-full border border-white/[0.12] bg-white/[0.03] p-0.5">
      {/* The fade sits on the strip, not on the capsule: masking the parent
          would eat its own border and background at the right edge. */}
      <div
        ref={scrollerRef}
        className="no-scrollbar flex min-w-0 flex-1 gap-1 overflow-x-auto [mask-image:linear-gradient(to_right,black_calc(100%-28px),transparent)]"
      >
        {items.map((item) => (
          <button
            key={item.key}
            ref={activeKey === item.key ? activeRef : undefined}
            type="button"
            onClick={() => onSelect(item.key)}
            className={`flex-1 shrink-0 cursor-pointer whitespace-nowrap rounded-full px-3 py-1.5 text-[12.5px] transition-colors ${
              activeKey === item.key
                ? "bg-accent text-primary"
                : "text-foreground/70 hover:bg-white/[0.06]"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
