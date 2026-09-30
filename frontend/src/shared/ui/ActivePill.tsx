import { motion } from "motion/react";

// Active highlight of a pill group. One layoutId per group, so the pill glides
// to the newly selected option instead of jumping.
export function ActivePill({ layoutId, bounceStrength }: { layoutId: string; bounceStrength: number }) {
  return (
    <motion.span
      aria-hidden
      layoutId={layoutId}
      variants={{ rest: { scale: 1 }, tap: { scale: 1 + 0.05 * bounceStrength } }}
      transition={{ type: "spring", stiffness: 420, damping: 36 }}
      className="absolute inset-0 rounded-full bg-accent"
    />
  );
}
