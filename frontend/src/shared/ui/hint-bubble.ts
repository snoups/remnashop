// Shared look of the floating hint bubble (FieldHint, Tooltip, the sidebar's rail hint): the glass
// dialog's material, 12px text at 1.5; they differ only in what they hang off and where it opens.
const HINT_BUBBLE_BASE_CLASS =
  "glass-dialog pointer-events-none absolute w-max max-w-64 rounded-2xl px-3.5 py-2.5 text-left text-[12px] font-normal normal-case leading-[1.5] tracking-normal opacity-0 transition-opacity duration-150";

export const HINT_BUBBLE_CLASS = `${HINT_BUBBLE_BASE_CLASS} text-foreground/90`;

/** The same bubble carrying an error's text. */
export const ERROR_HINT_BUBBLE_CLASS = `${HINT_BUBBLE_BASE_CLASS} text-error`;
