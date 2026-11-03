import { motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { useLoadGateSettling } from "@shared/lib/load-gate";

const DURATION_S = 0.2;
const UNCLIP_MARGIN_MS = 50;
// sizes arriving this close together are another animation inside (a spoiler): follow it, don't ease on top
const STREAM_GAP_MS = 40;

/** Eases its own height to whatever the content measures. Clips only while moving: a dropdown
 *  opened inside has to reach past the edge. */
export function AnimatedHeight({ children }: { children: ReactNode }) {
  const isSettling = useLoadGateSettling();
  const outerRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const [target, setTarget] = useState<{ height: number | "auto"; duration: number }>({ height: "auto", duration: 0 });

  useEffect(() => {
    const inner = innerRef.current;
    if (!inner) return;
    let current: number | null = null;
    let changedAt = -Infinity;
    let unclipTimer: ReturnType<typeof setTimeout> | undefined;
    const observer = new ResizeObserver(([entry]) => {
      const height = entry.contentRect.height;
      if (height === current) return;
      const now = performance.now();
      const isInstant = current === null || isSettling() || now - changedAt < STREAM_GAP_MS;
      const duration = isInstant ? 0 : DURATION_S;
      const outer = outerRef.current;
      // set before paint: React commits the new height a frame later
      if (current !== null && outer) {
        outer.style.overflow = "hidden";
        clearTimeout(unclipTimer);
        // a timer, not the animation's end: a size that bounces back before a render never animates
        unclipTimer = setTimeout(() => {
          outer.style.overflow = "";
        }, duration * 1000 + UNCLIP_MARGIN_MS);
      }
      current = height;
      changedAt = now;
      setTarget({ height, duration });
    });
    observer.observe(inner);
    return () => {
      observer.disconnect();
      clearTimeout(unclipTimer);
    };
  }, [isSettling]);

  return (
    <motion.div
      ref={outerRef}
      initial={false}
      animate={{ height: target.height }}
      transition={{ duration: target.duration, ease: "easeOut" }}
    >
      <div ref={innerRef} className="flex flex-col">
        {children}
      </div>
    </motion.div>
  );
}
