import type { HTMLMotionProps } from "motion/react";
import type { ReactNode } from "react";

import { Pressable } from "@shared/ui/Pressable";

interface ChoiceChipProps extends Omit<HTMLMotionProps<"button">, "children"> {
  children?: ReactNode;
  active: boolean;
  /** sm: dense grids (backup intervals) */
  size?: "md" | "sm";
  /** glass dialogs and popovers: glass button fills, 12/13px text */
  glass?: boolean;
  /** layout only (w-14, grid placement...) */
  className?: string;
}

/** One option of a small set (presets, strategies). */
export function ChoiceChip({
  active,
  size = "md",
  glass = false,
  className = "",
  type = "button",
  children,
  ...props
}: ChoiceChipProps) {
  return (
    <Pressable
      type={type}
      className={`flex items-center justify-center gap-1.5 whitespace-nowrap rounded-full border font-medium transition-colors ${
        size === "sm" ? `px-1.5 py-1 ${glass ? "text-[12px]" : "text-xs"}` : `px-3 py-1.5 ${glass ? "text-[13px]" : "text-[12.5px]"}`
      } disabled:cursor-not-allowed disabled:opacity-50 ${
        glass
          ? active
            ? "border-primary/35 bg-primary/15 text-primary"
            : "border-glass-border bg-white/[0.03] text-foreground/90 enabled:hover:bg-white/[0.06]"
          : active
            ? "border-primary/40 bg-accent text-primary"
            : "border-border text-foreground/80 enabled:hover:bg-white/[0.06]"
      } ${className}`}
      {...props}
    >
      {children}
    </Pressable>
  );
}
