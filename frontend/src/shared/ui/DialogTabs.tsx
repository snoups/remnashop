import { motion } from "motion/react";
import { useEffect, useId, useRef } from "react";
import type { ComponentType } from "react";

import { TAP_PILL_SCALE } from "@shared/lib/bounceState";
import { useHorizontalWheelScroll } from "@shared/lib/use-horizontal-wheel-scroll";
import { ActivePill } from "@shared/ui/ActivePill";
import { BounceIcon } from "@shared/ui/BounceIcon";

export interface DialogTabItem<T extends string> {
  key: T;
  label: string;
  icon: ComponentType<{ className?: string }>;
}

export function DialogTabs<T extends string>({
  items,
  activeKey,
  onSelect,
}: {
  items: DialogTabItem<T>[];
  activeKey: T;
  onSelect: (key: T) => void;
}) {
  const wheelRef = useHorizontalWheelScroll<HTMLDivElement>();
  const stripRef = useRef<HTMLDivElement | null>(null);
  const pillId = useId();

  // keep the active tab in view when the strip overflows; scrolls the strip only
  useEffect(() => {
    const strip = stripRef.current;
    const active = strip?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!strip || !active) return;
    strip.scrollTo({ left: active.offsetLeft - (strip.clientWidth - active.offsetWidth) / 2 });
  }, [activeKey]);

  // same shape as TabBar: the pill stays put, the tabs scroll inside it
  return (
    <div className="flex rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md">
      <motion.div
        layoutScroll
        ref={(el) => {
          stripRef.current = el;
          wheelRef(el);
        }}
        className="no-scrollbar flex min-w-0 flex-1 gap-1 overflow-x-auto rounded-full"
      >
        {items.map((item) => {
          const isActive = activeKey === item.key;
          return (
            <motion.button
              key={item.key}
              type="button"
              aria-selected={isActive}
              onClick={() => onSelect(item.key)}
              // flex-1 without min-w-0: equal widths while they fit, never narrower than the label
              className="group relative isolate block flex-1 rounded-full text-sm font-medium"
              initial="rest"
              whileHover="hover"
              whileTap="tap"
            >
              {isActive ? (
                <ActivePill layoutId={pillId} />
              ) : (
                <motion.span
                  variants={{ rest: { scale: 1 }, tap: { scale: TAP_PILL_SCALE } }}
                  className="absolute inset-0 rounded-full transition-colors group-hover:bg-white/[0.06]"
                />
              )}
              <span
                className={`relative z-10 flex h-[30px] items-center justify-center gap-1.5 whitespace-nowrap px-3.5 ${
                  isActive ? "text-primary" : "text-foreground"
                }`}
              >
                <BounceIcon icon={item.icon} size={16} hoverSize={20} />
                {item.label}
              </span>
            </motion.button>
          );
        })}
      </motion.div>
    </div>
  );
}
