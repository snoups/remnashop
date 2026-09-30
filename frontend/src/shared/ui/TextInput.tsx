import type { ComponentProps, ReactNode } from "react";

export const FIELD_SURFACE_CLASS = "border border-border bg-input/60 transition-colors";
const FIELD_TEXT_CLASS = "text-sm font-normal text-foreground outline-none";

// 38px form field; filters use the glass style instead (see SearchField)
const TEXT_FIELD_CLASS = `${FIELD_SURFACE_CLASS} ${FIELD_TEXT_CLASS} px-3 py-2 focus:border-primary aria-invalid:border-error aria-invalid:focus:border-error data-invalid-native:border-error data-invalid-native:focus:border-error disabled:cursor-not-allowed disabled:opacity-50`;

/** className: layout and padding tweaks only (w-full, flex-1, pr-10 for a trailing button...) */
export function TextInput({ className = "", ...props }: ComponentProps<"input">) {
  return <input className={`rounded-full ${TEXT_FIELD_CLASS} ${className}`} {...props} />;
}

export function TextArea({ className = "", ...props }: ComponentProps<"textarea">) {
  return <textarea className={`min-h-[38px] resize-none rounded-xl ${TEXT_FIELD_CLASS} ${className}`} {...props} />;
}

/** TextInput with a unit after the value ("дн.", "₽"); the suffix takes only its own width.
 *  className: layout only, goes on the wrapper. */
export function SuffixInput({
  suffix,
  className = "",
  ...props
}: ComponentProps<"input"> & { suffix: ReactNode }) {
  return (
    // label: a click on the suffix focuses the input too; state lives on the input, the border on the wrapper
    <label
      className={`flex cursor-text items-center rounded-full ${FIELD_SURFACE_CLASS} focus-within:border-primary has-[[aria-invalid=true]]:border-error has-[[aria-invalid=true]]:focus-within:border-error has-[[data-invalid-native]]:border-error has-[[data-invalid-native]]:focus-within:border-error has-disabled:cursor-not-allowed has-disabled:opacity-50 ${className}`}
    >
      <input
        className={`min-w-0 flex-1 bg-transparent py-2 pl-3 pr-2 last:pr-3 ${FIELD_TEXT_CLASS} [appearance:textfield] disabled:cursor-not-allowed [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none`}
        {...props}
      />
      {suffix != null && <span className="shrink-0 pr-3 text-[13px] text-muted-foreground">{suffix}</span>}
    </label>
  );
}
