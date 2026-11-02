import type { ReactNode } from "react";

/** As wide as `text` would be inside a field (13px, 14px sides): an invisible copy sets the width,
 *  the controls stretch over it. Lines up a row's controls with a field sized to its text. */
export function TextWidth({ text, className = "", children }: { text: string; className?: string; children: ReactNode }) {
  return (
    <div className={`inline-grid ${className}`}>
      <span className="invisible col-start-1 row-start-1 h-0 whitespace-pre px-3.5 text-[13px]">{text}</span>
      <div className="col-start-1 row-start-1 flex min-w-0 items-center gap-2">{children}</div>
    </div>
  );
}
