import { ChevronDown } from "lucide-react";
import type { ComponentType, FormEvent, ReactNode } from "react";

import { Collapse } from "@shared/ui/Collapse";
import { FieldHint } from "@shared/ui/FieldHint";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Pressable } from "@shared/ui/Pressable";

interface RowProps {
  icon?: ComponentType<{ className?: string }>;
  /** the circle's content instead of an icon: an emoji, a logo */
  glyph?: ReactNode;
  label: ReactNode;
  /** 12px muted line under the label */
  description?: ReactNode;
  /** FieldHint next to the label */
  hint?: string;
  /** controls on the right; keep them 32px tall (sm Button, sm Input), the Switch is its own case */
  children?: ReactNode;
  /** the whole row presses; its controls keep their own clicks */
  onClick?: () => void;
  /** set: a chevron after the text, turned while `panel` is open */
  expanded?: boolean;
  /** folds out under the row while expanded: Fields, one per line */
  panel?: ReactNode;
  /** the row is its own form (a panel with its own Save): Enter in a field submits it */
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void;
}

/** A 60px settings row in SectionRows: icon, label, controls. Every end item sits as far from the
 *  side as from top and bottom, on the pill's 30px curve: 32px items 14px in, the 28px switch 16px. */
export function Row({ icon, glyph, label, description, hint, children, onClick, expanded, panel, onSubmit }: RowProps) {
  const head = (
    <>
      <IconCircle icon={icon} glyph={glyph} />
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-[13px] font-medium leading-5 text-foreground">
            {label}
            {hint && <FieldHint text={hint} glass />}
          </p>
          {description && <div className="mt-0.5 text-[12px] leading-4 text-muted-foreground">{description}</div>}
        </div>
        {expanded !== undefined && (
          // 32px like the row's other small controls (the ? guide), a 14px chevron
          <span className="flex size-8 shrink-0 items-center justify-center">
            <ChevronDown className={`size-3.5 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`} />
          </span>
        )}
        {children && (
          // a control's click stays its own, not the row's
          <div className="flex shrink-0 items-center gap-2" onClick={(event) => event.stopPropagation()}>
            {children}
          </div>
        )}
      </div>
    </>
  );
  const corner = expanded && panel ? "rounded-[30px]" : "rounded-full";
  const headClass = "flex min-h-15 items-center gap-3 rounded-full px-3.5 has-[[data-switch]:last-child]:pr-4";
  const body = (
    <>
      {onClick ? (
        <Pressable as="div" onClick={onClick} className={`${headClass} transition-colors hover:bg-white/[0.04]`}>
          {head}
        </Pressable>
      ) : (
        <div className={headClass}>{head}</div>
      )}
      {/* 14px under the fields, as at their side */}
      <Collapse open={Boolean(expanded && panel)} className="flex flex-col gap-3 px-3.5 pb-3.5 pt-1">
        {panel}
      </Collapse>
    </>
  );
  // SectionRows' line sits on this box, so it bends with the pill; opened, the box outgrows
  // the pill and keeps the head's 30px corner
  return onSubmit ? (
    <form onSubmit={onSubmit} className={corner}>
      {body}
    </form>
  ) : (
    <div className={corner}>{body}</div>
  );
}
