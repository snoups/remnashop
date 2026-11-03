import type { HTMLMotionProps } from "motion/react";
import type { ReactNode } from "react";

import { Pressable } from "@shared/ui/Pressable";

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
  // floats on its own over a photo or a backdrop, with the glass of a card
  panel: "glass-panel enabled:hover:bg-white/[0.06]",
  default: "enabled:hover:bg-white/[0.06] enabled:hover:text-foreground",
  danger: "enabled:hover:bg-error/10 enabled:hover:text-error",
  // lights up with the surrounding `group` (a copyable field), not only on its own hover
  group: "enabled:group-hover:bg-white/[0.06] enabled:group-hover:text-foreground",
  // standalone header controls
  glass: "border border-glass-border bg-white/[0.05] enabled:hover:bg-white/[0.06] enabled:hover:text-foreground",
} as const;

interface IconButtonProps extends Omit<HTMLMotionProps<"button">, "children"> {
  children?: ReactNode;
  size: keyof typeof SIZE_CLASS;
  tone?: keyof typeof TONE_CLASS;
  /** layout and positioning only (absolute, -mr-1, cursor-grab...) */
  className?: string;
}

export function IconButton({
  size,
  tone = "default",
  className = "",
  type = "button",
  children,
  ...props
}: IconButtonProps) {
  return (
    <Pressable
      type={type}
      className={`flex shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${SIZE_CLASS[size]} ${TONE_CLASS[tone]} ${className}`}
      {...props}
    >
      {children}
    </Pressable>
  );
}
