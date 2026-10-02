import { motion, type HTMLMotionProps } from "motion/react";

import { bounceTap } from "@shared/lib/bounceState";

interface ChoiceChipProps extends HTMLMotionProps<"button"> {
  active: boolean;
  /** sm: dense grids (backup intervals) */
  size?: "md" | "sm";
  /** layout only (w-14, grid placement...) */
  className?: string;
}

/** One option of a small set (presets, strategies). */
export function ChoiceChip({ active, size = "md", className = "", type = "button", ...props }: ChoiceChipProps) {
  return (
    <motion.button
      type={type}
      {...bounceTap()}
      className={`flex items-center justify-center gap-1.5 whitespace-nowrap rounded-full border font-medium transition-colors ${
        size === "sm" ? "px-1.5 py-1 text-xs" : "px-3 py-1.5 text-[12.5px]"
      } disabled:cursor-not-allowed disabled:opacity-50 ${
        active ? "border-primary/40 bg-accent text-primary" : "border-border text-foreground/80 enabled:hover:bg-white/5"
      } ${className}`}
      {...props}
    />
  );
}
