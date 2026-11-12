import { Loader2, type LucideIcon } from "lucide-react";
import type { HTMLMotionProps } from "motion/react";
import type { ReactNode } from "react";

import { Pressable } from "@shared/ui/Pressable";

// secondary: card-header actions and buttons next to a field (14px semibold).
// glass: PillTabs' capsule fill, for actions beside one; glassAccent: its primary action, glassDanger:
// its destructive one (14px medium); glassSolid: full primary, the one action of a page like sign-in.
export type ButtonVariant = "secondary" | "glass" | "glassAccent" | "glassSolid" | "glassDanger";

const COLOR_CLASS: Record<ButtonVariant, string> = {
  secondary: "border-border text-foreground/90 hover:bg-white/[0.06]",
  glass: "border-glass-border bg-white/[0.03] text-foreground/90 hover:bg-white/[0.06]",
  glassAccent: "border-primary/35 bg-primary/15 text-primary hover:bg-primary/20",
  glassSolid:
    "border-transparent bg-primary text-primary-foreground shadow-[inset_0_1px_0_rgb(255_255_255/0.25)] hover:bg-primary-hover",
  glassDanger: "border-glass-border bg-white/[0.03] text-error hover:bg-error/10",
};

const TYPE_CLASS: Record<ButtonVariant, string> = {
  secondary: "px-3.5 text-sm font-semibold",
  glass: "px-3.5 text-sm font-medium",
  glassAccent: "px-3.5 text-sm font-medium",
  glassSolid: "px-3.5 text-sm font-semibold",
  glassDanger: "px-3.5 text-sm font-medium",
};

// sm: 32px, for actions inside list rows
const SM_TYPE_CLASS = "px-3 text-sm font-medium";

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
  // the glass pair keeps its 14px medium at every height
  const isGlass = variant.startsWith("glass");
  const typography = size === "sm" && !isGlass ? SM_TYPE_CLASS : TYPE_CLASS[variant];

  return (
    <Pressable
      type={type}
      className={`flex shrink-0 items-center justify-center gap-1.5 rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${SIZE_CLASS[size]} ${COLOR_CLASS[variant]} ${typography} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {/* glass buttons (36px, 14px text) take 16px icons, about the text's line height */}
      {isLoading ? (
        <Loader2 className={`${isGlass ? "size-4" : "size-3.5"} animate-spin`} />
      ) : (
        Icon && <Icon className={isGlass ? "size-4" : "size-3.5"} />
      )}
      {children}
    </Pressable>
  );
}
