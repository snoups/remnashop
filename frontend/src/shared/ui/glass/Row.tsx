import { ChevronDown } from "lucide-react";
import type { ComponentType, FormEvent, ReactNode } from "react";

import { Collapse } from "@shared/ui/Collapse";
import { FieldHint } from "@shared/ui/FieldHint";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Pressable } from "@shared/ui/Pressable";
import { INTERACTIVE_SELECTOR } from "@shared/ui/ripple-host";
import type { BadgeTone } from "@shared/ui/Badge";

interface RowProps {
  icon?: ComponentType<{ className?: string }>;
  /** the circle colored by status */
  tone?: BadgeTone;
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
  /** false: no chevron, the row still folds */
  chevron?: boolean;
  /** folds out under the row while expanded: Fields, one per line */
  panel?: ReactNode;
  /** the row is its own form (a panel with its own Save): Enter in a field submits it */
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void;
  /** sm: a 48px row in a dialog's DialogCard list: the 32px circle 8px in, a 20px badge 14px from the end,
   *  a 32px end button (data-row-button) 8px */
  size?: "md" | "sm";
}

const HEAD_CLASS = {
  md: "min-h-15 px-3.5 has-[[data-switch]:last-child]:pr-4",
  sm: "h-12 pl-2 pr-3.5 has-[[data-row-button]:last-child]:pr-2",
} as const;

/** A 60px settings row in SectionRows: icon, label, controls. Every end item sits as far from the
 *  side as from top and bottom, on the pill's 30px curve: 32px items 14px in, the 28px switch 16px. */
export function Row({ icon, tone, glyph, label, description, hint, children, onClick, expanded, chevron = true, panel, onSubmit, size = "md" }: RowProps) {
  const small = size === "sm";
  const head = (
    <>
      {(icon || glyph) && <IconCircle icon={icon} glyph={glyph} tone={tone} />}
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className={`flex items-center gap-1.5 text-sm font-medium text-foreground ${small ? "min-w-0 leading-tight" : "leading-5"}`}>
            {small && typeof label === "string" ? <span className="truncate">{label}</span> : label}
            {hint && <FieldHint text={hint} />}
          </p>
          {description && (
            <div className={`text-xs text-muted-foreground ${small ? "truncate leading-tight" : "mt-0.5 leading-4"}`}>{description}</div>
          )}
        </div>
        {expanded !== undefined && chevron && (
          // 32px like the row's other small controls (the ? guide), a 14px chevron
          <span className="flex size-8 shrink-0 items-center justify-center">
            <ChevronDown className={`size-3.5 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`} />
          </span>
        )}
        {children && (
          // a control's click stays its own, not the row's; a badge or a date presses the row
          <div
            className="flex shrink-0 items-center gap-2"
            onClick={(event) => {
              const control = (event.target as Element).closest(INTERACTIVE_SELECTOR);
              if (control && event.currentTarget.contains(control)) event.stopPropagation();
            }}
          >
            {children}
          </div>
        )}
      </div>
    </>
  );
  const corner = expanded && panel ? "rounded-[30px]" : "rounded-full";
  // a line under an sm row followed by another, as a page table's: an inset shadow takes no height
  const divider = small
    ? "[&:has(+[data-row-sm])]:shadow-[inset_0_-1px_0_color-mix(in_srgb,var(--color-border)_50%,transparent)]"
    : "";
  // group/row: an end item can react to the row's hover (a revoke button reddens)
  const headClass = `group/row flex items-center gap-3 rounded-full ${HEAD_CLASS[size]}`;
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
    <form onSubmit={onSubmit} data-row-sm={small || undefined} className={`${corner} ${divider}`}>
      {body}
    </form>
  ) : (
    <div data-row-sm={small || undefined} className={`${corner} ${divider}`}>
      {body}
    </div>
  );
}
