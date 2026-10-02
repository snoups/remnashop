import { motion, type HTMLMotionProps } from "motion/react";

import { bounceTap } from "@shared/lib/bounceState";

// size follows the container: equal inset on every side, concentric corners (see /dashboard/debug)
const SIZE_CLASS = {
  "18px": "size-[18px]",
  "5": "size-5",
  "6": "size-6",
  "26px": "size-[26px]",
  "7": "size-7",
  "8": "size-8",
  "9": "size-9",
  "9.5": "size-9.5",
} as const;

const TONE_CLASS = {
  default: "hover:bg-white/[0.06] hover:text-foreground",
  danger: "hover:bg-error/10 hover:text-error",
  // lights up with the surrounding `group` (a copyable field), not only on its own hover
  group: "group-hover:bg-white/[0.06] group-hover:text-foreground",
  // standalone header controls
  glass: "border border-glass-border bg-white/[0.05] hover:bg-white/[0.06] hover:text-foreground",
} as const;

interface IconButtonProps extends HTMLMotionProps<"button"> {
  size: keyof typeof SIZE_CLASS;
  tone?: keyof typeof TONE_CLASS;
  /** tap bounce multiplier (bounceTap's); omit for no bounce */
  bounce?: number;
  /** layout and positioning only (absolute, -mr-1, cursor-grab...) */
  className?: string;
}

export function IconButton({ size, tone = "default", bounce, className = "", type = "button", ...props }: IconButtonProps) {
  return (
    <motion.button
      type={type}
      {...(bounce !== undefined ? bounceTap(bounce) : {})}
      className={`flex shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${SIZE_CLASS[size]} ${TONE_CLASS[tone]} ${className}`}
      {...props}
    />
  );
}
