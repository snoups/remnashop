import { motion } from "motion/react";
import type { ComponentType, MouseEvent } from "react";
import { useEffect, useRef } from "react";
import { NavLink } from "react-router-dom";

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

// Re-navigating to the already-active tab still calls react-router's
// navigate() (even though the URL doesn't change), which resets Framer
// Motion's tap-gesture state on that link -- every tap after the first stops
// bouncing. Skipping navigation when already active keeps whileTap working.
function preventNavigationWhenActive(isActive: boolean) {
  return (event: MouseEvent) => {
    if (isActive) event.preventDefault();
  };
}

// A vertical mouse wheel does nothing on a horizontally-scrolling container
// by default (only trackpad swipes / shift+wheel do) -- redirect wheel input
// to horizontal scroll so a plain mouse wheel works too. React attaches
// onWheel as a passive listener, so preventDefault() there is silently
// ignored and the page scrolls too -- a plain addEventListener with
// `{ passive: false }` is required to actually stop that.
function useScrollTabsHorizontallyOnWheel<T extends HTMLElement>() {
  const ref = useRef<T>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onWheel = (event: WheelEvent) => {
      if (el.scrollWidth <= el.clientWidth) return;
      event.preventDefault();
      el.scrollLeft += event.deltaY;
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  return ref;
}

// The scale bounce lives on a separate background pill behind the icon/label,
// not on the link itself -- scaling the text via `transform` blurs it (same
// reasoning as BounceIcon avoiding transform for icons), so only the pill
// grows on tap while the content stays crisp and fixed-size.
function Tab({ to, end, icon, label, isActive, bounceStrength }: TabBarItem & { bounceStrength: number }) {
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
      <motion.span
        aria-hidden
        variants={{ rest: { scale: 1 }, tap: { scale: 1 + 0.05 * bounceStrength } }}
        className={`absolute inset-0 rounded-full transition-colors ${
          isActive ? "bg-accent" : "group-hover:bg-white/[0.06]"
        }`}
      />
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

export function TabBar({ items, bounceStrength }: { items: TabBarItem[]; bounceStrength: number }) {
  const tabsRef = useScrollTabsHorizontallyOnWheel<HTMLDivElement>();

  return (
    <nav className="inline-flex max-w-full rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md">
      {/* No padding/margin of its own -- stays inset by the pill's `p-1`
          evenly on all four sides, same as before scrolling was added, so
          this box is a smaller *concentric* capsule and its `rounded-full`
          clip boundary nests neatly inside the outer one instead of
          fighting it. `overflow-x-auto` forces `overflow-y` to `auto` too
          (CSS can't have one axis `auto` and the other `visible`), which
          can clip a tiny sliver of the hover/tap bounce's overshoot -- a
          fair trade for corners that actually line up. */}
      <div ref={tabsRef} className="no-scrollbar flex gap-1 overflow-x-auto rounded-full">
        {items.map(({ key, ...item }) => (
          <Tab key={key} {...item} bounceStrength={bounceStrength} />
        ))}
      </div>
    </nav>
  );
}
