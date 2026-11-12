// Shared by the nav list and the footer buttons (BuildInfoBadge, DonateButton), so they read as
// more nav rows; its own module, or the footer would import Sidebar.tsx in a cycle.
// Icon rail: a 40px circle, icon dead centre. Expanded: a full-width row whose
// icon keeps the same 12px inset on every side (40px - 16px icon, halved).
export const SIDEBAR_PILL_SHAPE_CLASSNAME =
  "flex size-10 shrink-0 items-center justify-center gap-2.5 self-center rounded-full text-sm xl:group-data-expanded/sidebar:w-auto xl:group-data-expanded/sidebar:self-stretch xl:group-data-expanded/sidebar:justify-start xl:group-data-expanded/sidebar:pl-3 xl:group-data-expanded/sidebar:pr-2.5";

export const SIDEBAR_PILL_CLASSNAME = `${SIDEBAR_PILL_SHAPE_CLASSNAME} font-medium text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground`;

// Labels show from `xl` up, and only while the sidebar is expanded
// (`data-expanded` on its aside); below that it's an icon rail.
// The mobile menu's row: the sidebar's row at a 44px touch height, the footer buttons included.
export const MOBILE_NAV_ROW_CLASSNAME =
  "flex min-h-11 w-full shrink-0 items-center gap-2.5 rounded-full px-3.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground";

export const LABEL_CLASSNAME = "hidden whitespace-nowrap xl:group-data-expanded/sidebar:inline";
