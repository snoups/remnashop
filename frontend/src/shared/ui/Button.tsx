import { Loader2, type LucideIcon } from "lucide-react";
import type { HTMLMotionProps } from "motion/react";
import type { ReactNode } from "react";

import { Pressable } from "@shared/ui/Pressable";

// accent/solid/outline/danger: primary and destructive actions, dialog and form footers (14px).
// secondary: card-header actions and buttons next to a field (12.5px semibold).
// glass: PillTabs' capsule fill, for actions beside one; glassAccent: its primary action, glassDanger:
// its destructive one (13px medium).
export type ButtonVariant =
  | "accent"
  | "solid"
  | "outline"
  | "secondary"
  | "glass"
  | "glassAccent"
  | "glassDanger"
  | "danger";

const COLOR_CLASS: Record<ButtonVariant, string> = {
  accent: "border-transparent bg-accent text-primary hover:bg-primary/20",
  solid: "border-transparent bg-primary text-primary-foreground hover:bg-primary-hover",
  outline: "border-border text-foreground/80 hover:bg-white/[0.06]",
  secondary: "border-border text-foreground/90 hover:bg-white/[0.06]",
  glass: "border-glass-border bg-white/[0.03] text-foreground/90 hover:bg-white/[0.06]",
  glassAccent: "border-primary/35 bg-primary/15 text-primary hover:bg-primary/20",
  glassDanger: "border-glass-border bg-white/[0.03] text-error hover:bg-error/10",
  danger: "border-border text-error hover:bg-error/10",
};

const TYPE_CLASS: Record<ButtonVariant, string> = {
  accent: "gap-1.5 px-4 text-sm font-medium",
  solid: "gap-1.5 px-4 text-sm font-semibold",
  outline: "gap-1.5 px-4 text-sm font-medium",
  secondary: "gap-1.5 px-3.5 text-[12.5px] font-semibold",
  glass: "gap-1.5 px-3.5 text-[13px] font-medium",
  glassAccent: "gap-1.5 px-3.5 text-[13px] font-medium",
  glassDanger: "gap-1.5 px-3.5 text-[13px] font-medium",
  danger: "gap-1.5 px-4 text-sm font-medium",
};

// sm: 32px, for actions inside list rows; one typography for every variant
const SM_TYPE_CLASS = "gap-1.5 px-3 text-[12.5px]";

// field: 38px, lines up with a text input in the same row
const SIZE_CLASS = { sm: "h-8", md: "h-9", field: "h-9.5" } as const;

interface ButtonProps extends HTMLMotionProps<"button"> {
  variant: ButtonVariant;
  size?: keyof typeof SIZE_CLASS;
  /** leading icon; a spinner takes its place while isLoading */
  icon?: LucideIcon;
  /** spinner before the label, button disabled */
  isLoading?: boolean;
  /** layout only (flex-1, w-full, mt-2...), no classes that fight the variant's */
  className?: string;
  children?: ReactNode;
}

export function Button({
  variant,
  size = "md",
  icon: Icon,
  isLoading = false,
  className = "",
  type = "button",
  disabled,
  children,
  ...props
}: ButtonProps) {
  // the glass pair keeps its 13px medium at every height
  const isGlass = variant === "glass" || variant === "glassAccent" || variant === "glassDanger";
  const typography =
    size === "sm" && !isGlass
      ? `${SM_TYPE_CLASS} ${variant === "danger" ? "font-semibold" : "font-medium"}`
      : TYPE_CLASS[variant];

  return (
    <Pressable
      type={type}
      className={`flex shrink-0 items-center justify-center rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${SIZE_CLASS[size]} ${COLOR_CLASS[variant]} ${typography} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {/* glass buttons (36px, 13px text) take 16px icons, about the text's line height */}
      {isLoading ? (
        <Loader2 className={`${isGlass ? "size-4" : "size-3.5"} animate-spin`} />
      ) : (
        Icon && <Icon className={isGlass ? "size-4" : "size-3.5"} />
      )}
      {children}
    </Pressable>
  );
}
