import { motion } from "motion/react";


// Active highlight of a pill group. One layoutId per group, so the pill glides
// to the newly selected option instead of jumping.
export function ActivePill({ layoutId }: { layoutId: string }) {
  return (
    <motion.span
      layoutId={layoutId}
      transition={{ type: "spring", stiffness: 420, damping: 36 }}
      // in style, not a class: Motion keeps the corners round through the glide only then
      style={{ borderRadius: 9999 }}
      className="absolute inset-0 bg-accent"
    />
  );
}
