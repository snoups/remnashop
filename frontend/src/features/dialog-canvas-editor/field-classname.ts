// Compact pill field for the editor panels, 36px like PillTabs and SelectDropdown size="compact".
// No border color: callers add border-glass-border (or an error color).
export const EDITOR_FIELD_CLASSNAME =
  "w-full rounded-full border bg-white/[0.03] h-9 px-3 text-[13px] font-medium text-foreground outline-none backdrop-blur-md transition-colors placeholder:font-normal hover:bg-white/[0.06] focus:border-primary disabled:opacity-50";

/** An editor panel's frame (canvas, inspectors); padding and layout are the caller's. */
export const EDITOR_PANEL_CLASSNAME = "rounded-2xl max-md:rounded-card border border-white/[0.08] bg-white/[0.03]";
