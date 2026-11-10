import type { ReactNode } from "react";

const TONE_CLASS = {
  success: "bg-success/15 text-success",
  warning: "bg-warning/15 text-warning",
  error: "bg-error/15 text-error",
} as const;

/** A section header's status at button height: a tint in the state's colour and a dot, no edge, so it
 *  doesn't read as one of the bordered buttons beside it. */
export function StatusPill({ tone, children }: { tone: keyof typeof TONE_CLASS; children: ReactNode }) {
  return (
    <span className={`flex h-9 shrink-0 items-center gap-1.5 rounded-full px-3.5 text-sm font-medium ${TONE_CLASS[tone]}`}>
      <span className="size-1.5 shrink-0 rounded-full bg-current" />
      {children}
    </span>
  );
}
