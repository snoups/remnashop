import { motion } from "motion/react";
import { useEffect, useId, useRef, type ComponentType, type MouseEvent } from "react";

import { useHorizontalWheelScroll } from "@shared/lib/use-horizontal-wheel-scroll";
import { ActivePill } from "@shared/ui/ActivePill";
import { MotionLink } from "@shared/ui/MotionLink";

export interface TabBarItem {
  key: string;
  to: string;
  icon: ComponentType<{ className?: string }>;
  label: string;
  isActive: boolean;
}

/** Route tabs in a 48px glass-panel capsule: 36px tabs 6px in, 13px medium. */
export function TabBar({ items }: { items: TabBarItem[] }) {
  const tabsRef = useHorizontalWheelScroll<HTMLDivElement>();
  const navRef = useRef<HTMLElement>(null);
  const activeKey = items.find((item) => item.isActive)?.key;
  const pillId = useId();

  // a deep link to a tab past the edge: scroll the strip only, scrollIntoView would move the page
  useEffect(() => {
    const active = navRef.current?.querySelector<HTMLElement>('[aria-current="page"]');
    const container = active?.parentElement;
    if (!container || !active) return;
    container.scrollTo({ left: active.offsetLeft - (container.clientWidth - active.offsetWidth) / 2 });
  }, [activeKey]);

  return (
    <nav ref={navRef} className="glass-panel inline-flex h-12 max-w-full rounded-full p-1.5">
      <motion.div ref={tabsRef} layoutScroll className="no-scrollbar flex gap-1 overflow-x-auto rounded-full">
        {items.map(({ key, to, icon: Icon, label, isActive }) => (
          <MotionLink
            key={key}
            to={to}
            aria-current={isActive ? "page" : undefined}
            // navigating to the active tab would only re-run navigate()
            onClick={(event: MouseEvent) => isActive && event.preventDefault()}
            className="group relative isolate flex h-9 shrink-0 items-center rounded-full text-[13px] font-medium"
          >
            {isActive ? (
              <ActivePill layoutId={pillId} />
            ) : (
              <span className="absolute inset-0 rounded-full transition-colors group-hover:bg-white/[0.06]" />
            )}
            <span
              className={`relative z-10 flex items-center gap-1.5 whitespace-nowrap px-4 ${
                isActive ? "text-primary" : "text-foreground"
              }`}
            >
              <Icon className="size-4 shrink-0" />
              {label}
            </span>
          </MotionLink>
        ))}
      </motion.div>
    </nav>
  );
}
