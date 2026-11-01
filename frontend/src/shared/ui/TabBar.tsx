import { motion } from "motion/react";
import { useEffect, useId, useRef } from "react";
import type { ComponentType, MouseEvent } from "react";

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

// Navigating to the active tab would only re-run navigate(), so it's skipped.
function preventNavigationWhenActive(isActive: boolean) {
  return (event: MouseEvent) => {
    if (isActive) event.preventDefault();
  };
}

function Tab({ to, icon: Icon, label, isActive, pillId }: TabBarItem & { pillId: string }) {
  return (
    <MotionLink
      to={to}
      aria-current={isActive ? "page" : undefined}
      onClick={preventNavigationWhenActive(isActive)}
      className="group relative isolate block shrink-0 rounded-full text-sm font-medium"
    >
      {isActive ? (
        <ActivePill layoutId={pillId} />
      ) : (
        <motion.span
          className="absolute inset-0 rounded-full transition-colors group-hover:bg-white/[0.06]"
        />
      )}
      <span
        className={`relative z-10 flex items-center gap-1.5 whitespace-nowrap px-4 py-2 ${
          isActive ? "text-primary" : "text-foreground"
        }`}
      >
        <Icon className="size-4 shrink-0" />
        {label}
      </span>
    </MotionLink>
  );
}

export function TabBar({ items }: { items: TabBarItem[] }) {
  const tabsRef = useHorizontalWheelScroll<HTMLDivElement>();
  const navRef = useRef<HTMLElement>(null);
  const activeKey = items.find((item) => item.isActive)?.key;
  const pillId = useId();

  // Deep link to a tab past the visible edge: bring it into view. Scrolls the
  // tab strip only, scrollIntoView would also move the page.
  useEffect(() => {
    const active = navRef.current?.querySelector<HTMLElement>('[aria-current="page"]');
    const container = active?.parentElement;
    if (!container || !active) return;
    container.scrollTo({
      left: active.offsetLeft - (container.clientWidth - active.offsetWidth) / 2,
    });
  }, [activeKey]);

  return (
    <nav ref={navRef} className="inline-flex max-w-full rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md">
      {/* No padding of its own: inset by the pill's `p-1`, it's a concentric
          capsule whose `rounded-full` clip nests in the outer one. */}
      <motion.div ref={tabsRef} layoutScroll className="no-scrollbar flex gap-1 overflow-x-auto rounded-full">
        {items.map(({ key, ...item }) => (
          <Tab key={key} {...item} pillId={pillId} />
        ))}
      </motion.div>
    </nav>
  );
}
