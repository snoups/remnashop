import type { HTMLAttributes } from "react";

/** Neutral pill for counts and metadata (durations, scopes, channels), not a status. */
export function Tag({ className = "", ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full bg-white/[0.06] px-2 py-0.5 text-[11px] font-semibold tabular-nums text-muted-foreground ${className}`}
      {...props}
    />
  );
}
