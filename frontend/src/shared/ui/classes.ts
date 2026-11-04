// Class strings shared by elements that are too different in structure for one component.

const GLASS_SURFACE_CLASS =
  "border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150";

/** Glass dropdown shell; padding is the caller's (p-1.5 for menus, p-3 for pickers). */
export const POPOVER_CLASS = `rounded-popover ${GLASS_SURFACE_CLASS}`;

/** An external link that reads as Button variant="glass"; grows in a row of links. */
export const GLASS_LINK_BUTTON_CLASS =
  "flex h-9 flex-1 items-center justify-center gap-1.5 rounded-full border border-glass-border bg-white/[0.03] px-3 text-[13px] font-medium text-foreground/90 transition-colors hover:bg-white/[0.06]";
/** Same for variant="glassSolid". */
export const GLASS_SOLID_LINK_BUTTON_CLASS =
  "flex h-9 items-center justify-center gap-1.5 rounded-full border border-transparent bg-primary px-3 text-[13px] font-semibold text-primary-foreground shadow-[inset_0_1px_0_rgb(255_255_255/0.25)] transition-colors hover:bg-primary-hover";

/** A settings card's glass straight over the shader, no panel under it to blur: sign-in and welcome. */
export const GLASS_STANDALONE_CARD_CLASS = "glass-panel rounded-3xl p-6 backdrop-blur-[28px] backdrop-saturate-150";

/** A card inside a Section (settings), its own 16px corners; layout and padding come from the caller. */
export const GLASS_INNER_CARD_CLASS = "rounded-2xl border border-white/[0.08] bg-white/[0.03]";

/** A card inside a glass dialog: 12px off its edge (p-3) with 12px corners, concentric with its 24px ones. */
export const GLASS_DIALOG_CARD_CLASS = "flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-white/[0.03] p-3.5";

/** A popover's scrolling list: content fades out over 8px at both ends, py matching the fade so nothing is
 *  faded at rest; the second gradient keeps the scrollbar column out of the fade. */
export const POPOVER_SCROLL_CLASS =
  "overflow-y-auto overflow-x-hidden py-2 [mask-composite:add] [mask-image:linear-gradient(to_bottom,transparent,black_8px,black_calc(100%-8px),transparent),linear-gradient(to_right,transparent_calc(100%-14px),black_calc(100%-14px))]";

/** The glass design's dropdown shell: the glass dialog's material (shared/ui/glass). */
export const GLASS_POPOVER_CLASS = "rounded-popover glass-dialog";

/** Glass panel of a dialog drawn without Modal (build info, donate). */
export const GLASS_DIALOG_CLASS = "rounded-dialog glass-dialog";

/** Section heading inside a details dialog card. */
export const SECTION_TITLE_CLASS =
  "flex items-center gap-1.5 px-2.5 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-foreground";

/** 11px uppercase label over a filter, column or stat. */
export const EYEBROW_CLASS = "text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";

/** Row-list table (transactions, event log...): header row, body, row. Rows add their own hover (enabled: on disableable buttons).
 *  The header is 14px in, as a settings Row, so the columns start over its rows' 32px circles. */
export const GLASS_LIST_HEAD_CLASS = `mb-1 border-b border-border px-3.5 pb-2.5 ${EYEBROW_CLASS}`;
// The divider between rows is an inset shadow, not divide-y: a border would add 1px to every row
// but the last, a shadow takes no height.
const LIST_DIVIDER_CLASS =
  "[&>*:not(:last-child)]:shadow-[inset_0_-1px_0_color-mix(in_srgb,var(--color-border)_50%,transparent)]";
// list-rows: rows fade in on mount (app/styles.css)
export const LIST_BODY_CLASS = `list-rows flex flex-col ${LIST_DIVIDER_CLASS}`;
// 36px icon + 12px inset on every side = concentric pill; taller content overflows instead of growing the row.
const LIST_ROW_SHAPE = "h-15 rounded-full [transition-property:background-color] duration-150";
export const LIST_ROW_CLASS = `${LIST_ROW_SHAPE} px-3`;
// a glass page's row, as a settings Row: a 32px circle 14px in on the 60px pill's curve
export const GLASS_LIST_ROW_CLASS = `${LIST_ROW_SHAPE} px-3.5`;
