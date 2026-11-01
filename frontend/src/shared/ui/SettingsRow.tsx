import { ChevronDown } from "lucide-react";
import type { ComponentType, ReactNode } from "react";

import { FieldHint } from "@shared/ui/FieldHint";
import { Pressable } from "@shared/ui/Pressable";

interface SettingsRowProps {
  icon?: ComponentType<{ className?: string }>;
  /** the circle's content instead of an icon: a logo, an emoji */
  glyph?: ReactNode;
  label: ReactNode;
  /** muted line under the label */
  description?: ReactNode;
  /** FieldHint next to the label */
  hint?: string;
  /** control on the right: Switch, PillTabs, an input; wraps under the label on a narrow card */
  children?: ReactNode;
  /** the whole row presses: opens details or folds out a panel; its own controls keep their clicks */
  onClick?: () => void;
  /** set: a chevron after the controls, turned while the panel below is open */
  expanded?: boolean;
}

/** Settings card row: icon, label, control. In a list, wrap the rows in SETTINGS_ROWS_CLASS. */
export function SettingsRow({ icon: Icon, glyph, label, description, hint, children, onClick, expanded }: SettingsRowProps) {
  const content = (
    <>
      <div className="flex min-w-0 flex-1 basis-48 items-center gap-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
          {glyph ?? (Icon && <Icon className="size-4" />)}
        </div>
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[13px] font-medium text-foreground">
            {label}
            {hint && <FieldHint text={hint} />}
          </p>
          {description && <p className="mt-0.5 text-[12px] text-muted-foreground">{description}</p>}
        </div>
      </div>
      {(children || expanded !== undefined) && (
        <div className="mr-1 flex min-w-0 max-w-full items-center gap-3">
          {children && (
            // a control's click stays its own, not the row's
            <div className="flex min-w-0 max-w-full items-center gap-3" onClick={(event) => event.stopPropagation()}>
              {children}
            </div>
          )}
          {expanded !== undefined && (
            <ChevronDown
              className={`size-4 shrink-0 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`}
            />
          )}
        </div>
      )}
    </>
  );
  // rounded-full like the OAuth provider rows: the list's border-b then tapers at both ends the same way
  const rowClass = "flex flex-wrap items-center gap-x-3 gap-y-2 rounded-full px-[12.5px] py-2.5";
  if (!onClick) return <div className={rowClass}>{content}</div>;
  return (
    <Pressable as="div" onClick={onClick} className={`${rowClass} transition-colors hover:bg-white/[0.04]`}>
      {content}
    </Pressable>
  );
}
