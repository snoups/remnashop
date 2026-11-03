import { motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { useLoadGateSettling } from "@shared/lib/load-gate";

const DURATION_S = 0.2;
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
    const observer = new ResizeObserver(([entry]) => {
      const height = entry.contentRect.height;
      if (height === current) return;
      const now = performance.now();
      const isInstant = current === null || isSettling() || now - changedAt < STREAM_GAP_MS;
      // set before paint: React commits the new height a frame later
      if (current !== null && outerRef.current) outerRef.current.style.overflow = "hidden";
      current = height;
      changedAt = now;
      setTarget({ height, duration: isInstant ? 0 : DURATION_S });
    });
    observer.observe(inner);
    return () => observer.disconnect();
  }, [isSettling]);

  return (
    <motion.div
      ref={outerRef}
      initial={false}
      animate={{ height: target.height }}
      transition={{ duration: target.duration, ease: "easeOut" }}
      onAnimationComplete={() => {
        if (outerRef.current) outerRef.current.style.overflow = "";
      }}
    >
      <div ref={innerRef} className="flex flex-col">
        {children}
      </div>
    </motion.div>
  );
}
