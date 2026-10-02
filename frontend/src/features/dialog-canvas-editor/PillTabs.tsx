import { motion } from "motion/react";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

import { TAP_PILL_SCALE } from "@shared/lib/bounceState";
import { useHorizontalWheelScroll } from "@shared/lib/use-horizontal-wheel-scroll";

interface PillTabsProps<T extends string> {
  items: { key: T; label: ReactNode }[];
  activeKey: T | null;
  onSelect: (key: T) => void;
  disabled?: boolean;
  /** field: 38px, lines up with a text input in the same row */
  size?: "compact" | "field";
}

/** The settings TabBar's capsule, for tabs that switch state instead of routes:
 * the editor's own tabs, the locale row, the inspector's pair. */
export function PillTabs<T extends string>({
  items,
  activeKey,
  onSelect,
  disabled = false,
  size = "compact",
}: PillTabsProps<T>) {
  const scrollerRef = useHorizontalWheelScroll<HTMLDivElement>();
  const activeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    // With twenty locales the selected one can sit past the right edge, and a
    // tab you cannot see reads as no selection at all.
    // Scrolls the strip itself, never the page: scrollIntoView would drag the
    // whole page down to an editor that sits below the fold.
    const active = activeRef.current;
    const scroller = active?.parentElement;
    if (!active || !scroller) return;
    const a = active.getBoundingClientRect();
    const s = scroller.getBoundingClientRect();
    if (a.left < s.left) scroller.scrollLeft -= s.left - a.left;
    else if (a.right > s.right) scroller.scrollLeft += a.right - s.right;
  }, [activeKey]);

  return (
    <div className="flex w-full rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md">
      <div ref={scrollerRef} className="no-scrollbar flex min-w-0 flex-1 gap-1 overflow-x-auto rounded-full">
        {items.map((item) => (
          <motion.button
            key={item.key}
            ref={activeKey === item.key ? activeRef : undefined}
            type="button"
            onClick={() => onSelect(item.key)}
            disabled={disabled}
            initial="rest"
            whileTap="tap"
            className="group relative isolate block flex-1 shrink-0 cursor-pointer rounded-full disabled:cursor-not-allowed disabled:opacity-50"
          >
            {/* Same split as TabBar: only the pill behind the label scales, so
                the text stays crisp through the bounce. */}
            <motion.span
              variants={{ rest: { scale: 1 }, tap: { scale: TAP_PILL_SCALE } }}
              className={`absolute inset-0 rounded-full transition-colors ${
                activeKey === item.key ? "bg-accent" : "group-hover:bg-white/[0.06]"
              }`}
            />
            <span
              className={`relative z-10 flex ${size === "field" ? "h-[28px]" : "h-[26px]"} items-center justify-center whitespace-nowrap px-3.5 text-[13px] font-medium ${activeKey === item.key ? "text-primary" : "text-foreground"}`}
            >
              {item.label}
            </span>
          </motion.button>
        ))}
      </div>
    </div>
  );
}
