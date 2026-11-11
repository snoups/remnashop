// Class strings shared by elements that are too different in structure for one component.

/** A dropdown's edge and shadow, under a frosted or an opaque fill. */
export const POPOVER_EDGE_CLASS =
  "rounded-popover border border-white/[0.14] shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)]";

/** Glass dropdown shell; padding is the caller's (p-1.5 for menus, p-3 for pickers). */
export const POPOVER_CLASS = `${POPOVER_EDGE_CLASS} bg-popover/60 backdrop-blur-2xl backdrop-saturate-150`;

/** An external link that reads as Button variant="glass"; grows in a row of links. */
export const GLASS_LINK_BUTTON_CLASS =
  "flex h-9 flex-1 items-center justify-center gap-1.5 rounded-full border border-glass-border bg-white/[0.03] px-3 text-sm font-medium text-foreground/90 transition-colors hover:bg-white/[0.06]";
/** Same for variant="glassSolid". */
export const GLASS_SOLID_LINK_BUTTON_CLASS =
  "flex h-9 items-center justify-center gap-1.5 rounded-full border border-transparent bg-primary px-3 text-sm font-semibold text-primary-foreground shadow-[inset_0_1px_0_rgb(255_255_255/0.25)] transition-colors hover:bg-primary-hover";

/** A settings card's glass straight over the shader, no panel under it to blur: sign-in and welcome. */
export const GLASS_STANDALONE_CARD_CLASS = "glass-panel rounded-3xl p-6 backdrop-blur-[28px] backdrop-saturate-150";

/** A card inside a Section (settings), its own 16px corners; layout and padding come from the caller. */
export const GLASS_INNER_CARD_CLASS = "rounded-2xl border border-white/[0.08] bg-white/[0.03]";

/** A plate with 12px corners: a glass dialog's card, or a block of the same look inside a card. */
export const GLASS_PLATE_CLASS = "rounded-xl border border-white/[0.08] bg-white/[0.03]";

/** A card inside a glass dialog: 12px off its edge (p-3) with 12px corners, concentric with its 24px ones. */
export const GLASS_DIALOG_CARD_CLASS = `flex flex-col gap-3 ${GLASS_PLATE_CLASS} p-3.5`;

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
  "flex items-center gap-1.5 px-2.5 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-foreground";

/** 12px uppercase label over a filter, column or stat. */
export const EYEBROW_CLASS = "text-xs font-semibold uppercase tracking-wide text-muted-foreground";

/** Row-list table (transactions, event log...): header row, body, row. Rows add their own hover (enabled: on disableable buttons).
 *  The header is 14px in, as a settings Row, so the columns start over its rows' 32px circles. */
export const GLASS_LIST_HEAD_CLASS = `mb-1 border-b border-border px-3.5 pb-2.5 ${EYEBROW_CLASS}`;
// The divider between rows is an inset shadow, not divide-y: a border would add 1px to every row
// but the last, a shadow takes no height.
const LIST_DIVIDER_CLASS =
  "[&>*:not(:last-child)]:shadow-[inset_0_-1px_0_color-mix(in_srgb,var(--color-border)_50%,transparent)]";
// list-rows: rows fade in on mount (app/styles.css)
/** A row table's horizontal scroller, its min-w child set by the table. overflow-y-hidden: overflow-x-auto alone makes y
 *  scrollable too, and the rows' rise-in would flash a scrollbar; the 8px/4px bleed keeps row edges and focus rings unclipped. */
export const LIST_SCROLL_X_CLASS = "-mx-2 -my-1 overflow-x-auto overflow-y-hidden px-2 py-1";
export const LIST_BODY_CLASS = `list-rows flex flex-col ${LIST_DIVIDER_CLASS}`;
// a glass page's row, as a settings Row: a 32px circle 14px in on the 60px pill's curve; taller content overflows
export const GLASS_LIST_ROW_CLASS = "h-15 rounded-full px-3.5 [transition-property:background-color] duration-150";

/** A dashboard page that runs its own scroller instead of main's: the root, its bar and its scroller. */
export const PAGE_CLASS = "relative flex flex-1 flex-col md:min-h-0 md:pr-[var(--scrollbar-size)] md:-mb-5";
/** The bar over the page's scroller: floats over its top on desktop, the 48px the scroller's 68px assumes. */
export const PAGE_BAR_CLASS = "md:absolute md:left-0 md:right-[var(--scrollbar-size)] md:top-0 md:z-10";
/** The bar as a glass filter strip. */
export const PAGE_TOOLBAR_CLASS = `glass-panel flex shrink-0 flex-wrap items-center gap-2 rounded-3xl p-1.5 md:flex-nowrap ${PAGE_BAR_CLASS}`;
/** The search in a toolbar: takes the free space, never narrower than 256px on desktop so it outweighs a filter. */
export const PAGE_TOOLBAR_SEARCH_CLASS = "flex min-w-40 flex-1 md:min-w-64";
const PAGE_SCROLL_BASE_CLASS =
  "scroll-fade-y scroll-fade-gap page-scroll md:min-h-0 md:flex-1 md:overflow-y-auto [--fade-bottom-size:0px] [scrollbar-gutter:stable] max-md:[scrollbar-gutter:auto] max-md:[scrollbar-width:none] max-md:[&::-webkit-scrollbar]:hidden md:-mr-5 md:pb-5 md:pr-[calc(1.25rem-var(--scrollbar-size))]";
/** Scroller under PAGE_BAR_CLASS: a 20px gap under the bar, where the top fade sits (from 48px); content starts at 68px. */
export const PAGE_SCROLL_UNDER_BAR_CLASS = `${PAGE_SCROLL_BASE_CLASS} mt-1 pt-2 md:mt-0 md:pt-[68px] md:scroll-pt-[68px] [--fade-rest-start:48px]`;
/** Scroller of a page without a bar (data-under-header): the header's 20px padding moves in here. */
export const PAGE_SCROLL_CLASS = `${PAGE_SCROLL_BASE_CLASS} md:pt-5 md:scroll-pt-5`;

/** A glass dialog's body that holds cards or plates: 12px in, for their 12px corners. */
export const GLASS_DIALOG_PAD_CLASS = "p-3 [--dialog-pad:0.75rem]";
/** A glass dialog's scroller; padding is the caller's (p-4 for plain text). */
export const GLASS_DIALOG_SCROLL_CLASS = "scroll-fade-y min-h-0 flex-1 overflow-y-auto";
/** A glass dialog's scrolling body of cards. */
export const GLASS_DIALOG_BODY_CLASS = `${GLASS_DIALOG_SCROLL_CLASS} ${GLASS_DIALOG_PAD_CLASS}`;
/** A glass dialog's footer, 16px in; alignment and shrink-0 are the caller's. */
export const GLASS_DIALOG_FOOTER_CLASS = "flex gap-2 border-t border-white/[0.08] p-4";

/** The hover wash of a tab or pill, under its label; the parent is the `group`. */
export const TAB_HOVER_CLASS = "absolute inset-0 rounded-full transition-colors group-hover:bg-white/[0.06]";

/** A headline number: a KPI tile's value and the dashboard cards' totals; color is the caller's. */
export const KPI_VALUE_CLASS = "text-2xl font-bold tabular-nums tracking-tight";

/** A row's number between body text and a KPI: funnel steps, retention weeks; color is the caller's. */
export const STAT_VALUE_CLASS = "text-base font-bold tabular-nums";

/** The title of a full-screen card or story: sign-in, welcome, password change, error screens, announcements. */
export const SCREEN_TITLE_CLASS = "text-xl font-bold tracking-tight text-foreground";

/** The formatting toolbar over a text editor's field, and the divider between its groups. */
export const TEXT_TOOLBAR_CLASS = "flex flex-wrap items-center gap-0.5 border-b border-border px-2 py-1.5";
export const TEXT_TOOLBAR_DIVIDER_CLASS = "mx-1.5 h-4 w-px bg-border";

/** A picker field's leading icon, lit on hover and focus of its `group` trigger. */
export const PICKER_ICON_CLASS =
  "pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors group-not-focus:group-hover:text-foreground group-focus:text-primary";
