import { motion } from "motion/react";

import { TAP_PILL_SCALE } from "@shared/lib/bounceState";

// Active highlight of a pill group. One layoutId per group, so the pill glides
// to the newly selected option instead of jumping.
export function ActivePill({ layoutId }: { layoutId: string }) {
  return (
    <motion.span
      layoutId={layoutId}
      variants={{ rest: { scale: 1 }, tap: { scale: TAP_PILL_SCALE } }}
      transition={{ type: "spring", stiffness: 420, damping: 36 }}
      className="absolute inset-0 rounded-full bg-accent"
    />
  );
}
