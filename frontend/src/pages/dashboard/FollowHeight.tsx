import type { ReactNode } from "react";

// a lone card spans the row
export const PAIR_ROW_CLASS = "@container grid grid-cols-[repeat(auto-fit,minmax(min(100%,440px),1fr))] gap-5";

/** In a PAIR_ROW_CLASS row: side by side (2 × 440 + gap) the card takes its neighbour's height and
 *  scrolls inside; stacked it grows. The card needs className="min-h-0 flex-1" and a scrolling body. */
export function FollowHeight({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex flex-col">
      <div className="flex flex-1 flex-col @min-[900px]:absolute @min-[900px]:inset-0">{children}</div>
    </div>
  );
}
