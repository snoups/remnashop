import { motion, type HTMLMotionProps } from "motion/react";

import { bounceTap } from "@shared/lib/bounceState";

// accent/solid/outline/danger: primary and destructive actions, dialog and form footers (14px).
// secondary: card-header actions and buttons next to a field (12.5px semibold).
export type ButtonVariant = "accent" | "solid" | "outline" | "secondary" | "danger";

const COLOR_CLASS: Record<ButtonVariant, string> = {
  accent: "border-transparent bg-accent text-primary hover:bg-primary/20",
  solid: "border-transparent bg-primary text-primary-foreground hover:bg-primary-hover",
  outline: "border-border text-foreground/80 hover:bg-white/5",
  secondary: "border-border text-foreground/90 hover:bg-white/5",
  danger: "border-border text-error hover:bg-error/10",
};

const TYPE_CLASS: Record<ButtonVariant, string> = {
  accent: "gap-1.5 px-4 text-sm font-medium",
  solid: "gap-1.5 px-4 text-sm font-semibold",
  outline: "gap-1.5 px-4 text-sm font-medium",
  secondary: "gap-1.5 px-3.5 text-[12.5px] font-semibold",
  danger: "gap-1.5 px-4 text-sm font-medium",
};

// sm: 32px, for actions inside list rows; one typography for every variant
const SM_TYPE_CLASS = "gap-1.5 px-3 text-[12.5px]";

// field: 38px, lines up with a text input in the same row
const SIZE_CLASS = { sm: "h-8", md: "h-9", field: "h-9.5" } as const;

interface ButtonProps extends HTMLMotionProps<"button"> {
  variant: ButtonVariant;
  size?: keyof typeof SIZE_CLASS;
  /** layout only (flex-1, w-full, mt-2...), no classes that fight the variant's */
  className?: string;
}

export function Button({ variant, size = "md", className = "", type = "button", ...props }: ButtonProps) {
  const typography =
    size === "sm" ? `${SM_TYPE_CLASS} ${variant === "danger" ? "font-semibold" : "font-medium"}` : TYPE_CLASS[variant];

  return (
    <motion.button
      type={type}
      {...bounceTap()}
      className={`flex shrink-0 items-center justify-center rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${SIZE_CLASS[size]} ${COLOR_CLASS[variant]} ${typography} ${className}`}
      {...props}
    />
  );
}
