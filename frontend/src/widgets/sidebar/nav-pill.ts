// Pill styling shared between the nav list (Sidebar.tsx) and the footer
// buttons (BuildInfoBadge, DonateButton) so they read as more nav rows,
// not a visually distinct block. Split into its own module so those footer
// widgets don't import Sidebar.tsx directly and create a cycle.
export const SIDEBAR_PILL_CLASSNAME =
  "flex items-center justify-center gap-2.5 rounded-full py-2.5 pl-3.5 pr-2.5 text-[13.5px] font-medium text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground lg:justify-start";

// Below `lg` there's no room for text labels next to the icons — the sidebar
// collapses to an icon rail instead (matches DESKTOP_BREAKPOINT elsewhere).
export const LABEL_CLASSNAME = "hidden lg:inline";
