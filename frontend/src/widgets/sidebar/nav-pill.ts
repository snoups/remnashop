// Pill styling shared between the nav list (Sidebar.tsx) and the footer
// buttons (BuildInfoBadge, DonateButton) so they read as more nav rows,
// not a visually distinct block. Split into its own module so those footer
// widgets don't import Sidebar.tsx directly and create a cycle.
// Icon rail: a 40px circle, icon dead centre. Expanded: a full-width row whose
// icon keeps the same 11.5px inset on every side (40px - 17px icon, halved).
export const SIDEBAR_PILL_SHAPE_CLASSNAME =
  "flex size-10 shrink-0 items-center justify-center gap-2.5 self-center rounded-full text-[13.5px] xl:group-data-expanded/sidebar:w-auto xl:group-data-expanded/sidebar:self-stretch xl:group-data-expanded/sidebar:justify-start xl:group-data-expanded/sidebar:pl-[11.5px] xl:group-data-expanded/sidebar:pr-2.5";

export const SIDEBAR_PILL_CLASSNAME = `${SIDEBAR_PILL_SHAPE_CLASSNAME} font-medium text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground`;

// Labels show from `xl` up, and only while the sidebar is expanded
// (`data-expanded` on its aside); below that it's an icon rail.
export const LABEL_CLASSNAME = "hidden whitespace-nowrap xl:group-data-expanded/sidebar:inline";
