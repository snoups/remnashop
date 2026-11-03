import type { ComponentType, ReactNode } from "react";

import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { IconCircle } from "@shared/ui/glass/IconCircle";

interface SectionProps {
  /** a target for links (#access); the scroller's scroll-padding decides where it lands */
  id?: string;
  icon: ComponentType<{ className?: string }>;
  /** a badge may follow the text (Beta) */
  title: ReactNode;
  description: string;
  /** actions on the right of the header, 36px tall like its icon: a Button with an icon, PillTabs, StatusPill */
  aside?: ReactNode;
  /** under the content: SaveFooter variant="glassAccent"; omit when there's nothing to save */
  footer?: ReactNode;
  /** content edge to edge under the header line, padding its own (an editor's columns) */
  flush?: boolean;
  /** fills a grid cell: its row sets the height, so the content can't ease it */
  stretched?: boolean;
  /** layout only (flex-1, min-h-0) */
  className?: string;
  children: ReactNode;
}

/** A settings card: header (icon, 15px title, description, actions), a line across, then
 *  SectionRows / SectionFields, then the footer. glass-panel, 24px corners, 16px inset. */
export function Section({ id, icon, title, description, aside, footer, flush = false, stretched = false, className = "", children }: SectionProps) {
  return (
    <section id={id} className={`glass-panel flex flex-col rounded-3xl ${flush ? "overflow-hidden" : "p-4"} ${className}`}>
      <header className={`flex flex-wrap items-center gap-3 ${flush ? "px-4 pt-4" : ""}`}>
        <IconCircle icon={icon} header />
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-2 text-[15px] font-semibold tracking-tight text-foreground">{title}</h2>
          <p className="mt-0.5 text-[12px] text-muted-foreground">{description}</p>
        </div>
        {/* shrink-0: a w-full control (PillTabs) would otherwise share the line with the title */}
        {aside && <div className="flex shrink-0 items-center gap-2">{aside}</div>}
      </header>
      <div className={`mt-4 border-t border-white/[0.08] ${flush ? "" : "-mx-4"}`} />
      {stretched ? (
        <>
          {children}
          {footer}
        </>
      ) : (
        <AnimatedHeight>
          {children}
          {footer}
        </AnimatedHeight>
      )}
    </section>
  );
}

// a thin line between rows; a Row's pill makes its border bend at both ends
const ROWS_CLASS = "flex flex-col [&>*:not(:last-child)]:border-b [&>*:not(:last-child)]:border-border/50";

/** Rows of one Section: Row, a line between each. divided: a line above, 8px either side of it,
 *  when it follows SectionFields (the mirror of SectionFields divided after rows). flush: no margin
 *  of its own, outside a Section. */
export function SectionRows({ divided = false, flush = false, children }: { divided?: boolean; flush?: boolean; children: ReactNode }) {
  const spacing = flush ? "" : divided ? "mt-2 border-t border-white/[0.08] pt-2" : "mt-4";
  return <div className={`${spacing} ${ROWS_CLASS}`}>{children}</div>;
}

/** A block of Fields in a Section, one per line, edges on the rows' icons. divided: a line above,
 *  when it follows SectionRows. */
export function SectionFields({ divided = false, children }: { divided?: boolean; children: ReactNode }) {
  return (
    <div className={divided ? "mt-2 border-t border-white/[0.08] pt-2" : "mt-4"}>
      <div className="flex flex-col gap-3 px-3.5 pb-2 pt-1">{children}</div>
    </div>
  );
}
