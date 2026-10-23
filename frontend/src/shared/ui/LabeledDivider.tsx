import type { ReactNode } from "react";

import { EYEBROW_CLASS } from "@shared/ui/classes";

/** Horizontal rule with an eyebrow label in the middle ("or", a section name). */
export function LabeledDivider({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-px flex-1 bg-border" />
      <span className={`whitespace-nowrap ${EYEBROW_CLASS}`}>{children}</span>
      <div className="h-px flex-1 bg-border" />
    </div>
  );
}
