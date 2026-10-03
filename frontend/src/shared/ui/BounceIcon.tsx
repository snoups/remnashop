import { motion } from "motion/react";
import type { ComponentType } from "react";

import { BOUNCE_STRENGTH } from "@shared/lib/bounceState";

interface BounceIconProps {
  icon: ComponentType<{ className?: string }>;
  size: number;
  hoverSize: number;
  className?: string;
}

/**
 * Icon that grows on hover via a spring, not `transform: scale` — scaling an
 * SVG this small via transform blurs it (the browser rasterizes it at rest
 * size and stretches that texture instead of re-rendering the vector).
 * Animating width/height re-renders it crisp at every frame.
 *
 * The growing element is absolutely positioned inside a placeholder sized to
 * the REST size, so its growth never affects the parent row's layout — only
 * the icon itself visually grows from its own center.
 *
 * Centered via translate, not `inset-0` + `margin: auto`: past the placeholder's
 * size, auto margins can't go negative (CSS2.1 10.3.7) and growth drifts left.
 *
 * Doesn't trigger its own hover: it reads the "hover"/"rest" variant from an
 * ancestor motion component (`initial="rest" whileHover="hover"`), so the
 * whole row triggers it, not just the icon's own small hit area.
 */
export function BounceIcon({ icon: Icon, size, hoverSize, className = "" }: BounceIconProps) {
  const scaledHover = size + (hoverSize - size) * BOUNCE_STRENGTH;

  return (
    <span className="relative inline-block shrink-0" style={{ width: size, height: size }}>
      <motion.span
        className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center justify-center"
        // the rest size as a plain style too: under AnimatePresence initial={false}
        // (every dashboard page) the "rest" variant is never applied, and the icon
        // collapsed to the SVG's default size
        style={{ width: size, height: size }}
        variants={{
          rest: { width: size, height: size },
          hover: { width: scaledHover, height: scaledHover },
          tap: { width: scaledHover, height: scaledHover },
        }}
        // Critically damped (damping = 2·sqrt(stiffness) at mass 1): avoids
        // the overshoot an underdamped spring settling from rest would have.
        // Doesn't cover a spring retargeted mid-flight (rapid hover in/out),
        // which can still dip below `size` for a frame even at this
        // damping — `overflow-visible` below is the actual guard against
        // that clipping the icon's edge against the SVG's default
        // `overflow: hidden`.
        transition={{ type: "spring", stiffness: 400, damping: 40 }}
      >
        <Icon className={`size-full overflow-visible ${className}`} />
      </motion.span>
    </span>
  );
}
