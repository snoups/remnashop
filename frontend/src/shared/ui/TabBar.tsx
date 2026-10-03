import { motion } from "motion/react";
import { useEffect, useId, useRef } from "react";
import type { ComponentType, MouseEvent } from "react";
import { NavLink } from "react-router-dom";

import { TAP_PILL_SCALE } from "@shared/lib/bounceState";
import { useHorizontalWheelScroll } from "@shared/lib/use-horizontal-wheel-scroll";
import { ActivePill } from "@shared/ui/ActivePill";
import { BounceIcon } from "@shared/ui/BounceIcon";

const MotionNavLink = motion.create(NavLink);

export interface TabBarItem {
  key: string;
  to: string;
  end?: boolean;
  icon: ComponentType<{ className?: string }>;
  label: string;
  isActive: boolean;
}

// Navigating to the active tab still runs navigate(), which resets Motion's
// tap state on that link and kills every later bounce, so it's skipped.
function preventNavigationWhenActive(isActive: boolean) {
  return (event: MouseEvent) => {
    if (isActive) event.preventDefault();
  };
}

// The bounce is on a pill behind the icon and label: scaling text with
// `transform` blurs it.
function Tab({ to, end, icon, label, isActive, pillId }: TabBarItem & { pillId: string }) {
  return (
    <MotionNavLink
      to={to}
      end={end}
      onClick={preventNavigationWhenActive(isActive)}
      className="group relative isolate block shrink-0 rounded-full text-sm font-medium"
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
        className={`relative z-10 flex items-center gap-1.5 whitespace-nowrap px-4 py-2 ${
          isActive ? "text-primary" : "text-foreground"
        }`}
      >
        <BounceIcon icon={icon} size={16} hoverSize={20} />
        {label}
      </span>
    </MotionNavLink>
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
          capsule whose `rounded-full` clip nests in the outer one.
          `overflow-x-auto` forces `overflow-y: auto`, which may clip a sliver
          of the bounce's overshoot. */}
      <motion.div ref={tabsRef} layoutScroll className="no-scrollbar flex gap-1 overflow-x-auto rounded-full">
        {items.map(({ key, ...item }) => (
          <Tab key={key} {...item} pillId={pillId} />
        ))}
      </motion.div>
    </nav>
  );
}
