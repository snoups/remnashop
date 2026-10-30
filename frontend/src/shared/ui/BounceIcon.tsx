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
 * Icon that grows on hover by animating width/height: `transform: scale`
 * blurs a small SVG. It sits inside a rest-sized placeholder, so the row's
 * layout never moves, and flex centering spills it evenly past the
 * placeholder's edges. No translate: Firefox snaps a transform that stops
 * changing to whole pixels, and the icon jumps once the animation settles.
 *
 * Takes the "hover"/"rest" variant from an ancestor motion component, so the
 * whole row triggers it.
 */
export function BounceIcon({ icon: Icon, size, hoverSize, className = "" }: BounceIconProps) {
  const scaledHover = size + (hoverSize - size) * BOUNCE_STRENGTH;

  return (
    <span className="inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}>
      <motion.span
        className="flex shrink-0 items-center justify-center"
        // also as a plain style: under AnimatePresence initial={false} (every
        // dashboard page) the "rest" variant is never applied
        style={{ width: size, height: size }}
        variants={{
          rest: { width: size, height: size },
          hover: { width: scaledHover, height: scaledHover },
          tap: { width: scaledHover, height: scaledHover },
        }}
        // critically damped, so no overshoot; a spring retargeted mid-flight
        // can still dip below `size`, which `overflow-visible` keeps unclipped
        transition={{ type: "spring", stiffness: 400, damping: 40 }}
      >
        <Icon className={`size-full overflow-visible ${className}`} />
      </motion.span>
    </span>
  );
}
