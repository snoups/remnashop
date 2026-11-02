// Shared look of the floating hint bubble; FieldHint and Tooltip differ only
// in what they hang off and where the bubble opens.
export const HINT_BUBBLE_CLASS =
  "pointer-events-none absolute w-max max-w-56 rounded-popover-item border border-white/[0.14] bg-popover px-3 py-2 text-left text-xs font-normal normal-case tracking-normal text-foreground opacity-0 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6)] transition-opacity duration-150";

/** The glass design's bubble: the glass dialog's material, 12px text at 1.5. */
export const GLASS_HINT_BUBBLE_CLASS =
  "glass-dialog pointer-events-none absolute w-max max-w-64 rounded-2xl px-3.5 py-2.5 text-left text-[12px] font-normal normal-case leading-[1.5] tracking-normal text-foreground/90 opacity-0 transition-opacity duration-150";
