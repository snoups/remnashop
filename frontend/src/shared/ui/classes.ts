// Class strings shared by elements that are too different in structure for one component.

const GLASS_SURFACE_CLASS =
  "border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150";

/** Glass dropdown shell; padding is the caller's (p-1.5 for menus, p-3 for pickers). */
export const POPOVER_CLASS = `rounded-popover ${GLASS_SURFACE_CLASS}`;

/** The glass design's dropdown shell: the glass dialog's material (shared/ui/glass). */
export const GLASS_POPOVER_CLASS = "rounded-popover glass-dialog";

/** Glass panel of a dialog drawn without Modal (build info, donate). */
export const GLASS_DIALOG_CLASS = `rounded-dialog ${GLASS_SURFACE_CLASS}`;

/** Section heading inside a details dialog card. */
export const SECTION_TITLE_CLASS =
  "flex items-center gap-1.5 px-2.5 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-foreground";

/** 11px uppercase label over a filter, column or stat. */
export const EYEBROW_CLASS = "text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";

/** Row-list table (admins, transactions, event log...): header row, body, row. Rows add their own hover (enabled: on disableable buttons). */
export const LIST_HEAD_CLASS = `mb-1 border-b border-border px-3 pb-2.5 ${EYEBROW_CLASS}`;
// The divider between rows is an inset shadow, not divide-y: a border would add 1px to every row
// but the last, a shadow takes no height. For containers that aren't LIST_BODY_CLASS (the admins grid).
export const LIST_DIVIDER_CLASS =
  "[&>*:not(:last-child)]:shadow-[inset_0_-1px_0_color-mix(in_srgb,var(--color-border)_50%,transparent)]";
// list-rows: rows fade in on mount (app/styles.css)
export const LIST_BODY_CLASS = `list-rows flex flex-col ${LIST_DIVIDER_CLASS}`;
// 36px icon + 12px inset on every side = concentric pill; taller content overflows instead of growing the row.
export const LIST_ROW_CLASS = "h-15 rounded-full px-3 [transition-property:background-color] duration-150";

/** Settings card: rows of one section, a thin line between them (SettingsRow, OAuth providers). */
export const SETTINGS_ROWS_CLASS =
  "flex flex-col [&>*:not(:last-child)]:border-b [&>*:not(:last-child)]:border-border/50";
/** Settings card: the line that starts the next section. */
export const SETTINGS_SECTION_CLASS = "mt-2 border-t border-white/[0.08] pt-2";
