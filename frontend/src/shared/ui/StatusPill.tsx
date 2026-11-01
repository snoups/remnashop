import type { ReactNode } from "react";

const TONE_CLASS = {
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  error: "bg-error/10 text-error",
} as const;

/** Card-header status at button height (bot, push): a tinted pill, not an uppercase Badge. */
export function StatusPill({ tone, children }: { tone: keyof typeof TONE_CLASS; children: ReactNode }) {
  return (
    <span
      className={`flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-transparent px-4 text-[13px] font-semibold ${TONE_CLASS[tone]}`}
    >
      {children}
    </span>
  );
}
