import type { ReactNode } from "react";

/** 32px label in a Row: a count or a state next to its control; md: 36px, in a dialog header. Sunken by
 *  default; subtle: a faint fill over the surface, for a row of several. */
export function Tag({
  subtle = false,
  size = "sm",
  children,
}: {
  subtle?: boolean;
  size?: "sm" | "md";
  children: ReactNode;
}) {
  return (
    <span
      className={`flex ${size === "md" ? "h-9" : "h-8"} shrink-0 items-center rounded-full px-3 text-[11px] font-medium text-muted-foreground ${
        subtle ? "bg-white/[0.05]" : "glass-well"
      }`}
    >
      {children}
    </span>
  );
}
