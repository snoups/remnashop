import type { ComponentProps } from "react";

import { useRequiredInputProps } from "@shared/ui/field-context";

// 38px field of the dialog editor; glass forms use glass/Input, filters SearchField
const TEXT_FIELD_CLASS =
  "border border-border bg-input/60 transition-colors text-sm font-normal text-foreground outline-none px-3 py-2 focus:border-primary aria-invalid:border-error aria-invalid:focus:border-error data-invalid-native:border-error data-invalid-native:focus:border-error disabled:cursor-not-allowed disabled:opacity-50";

/** className: layout and padding tweaks only (w-full, flex-1, pr-10 for a trailing button...) */
export function TextInput({ className = "", ...props }: ComponentProps<"input">) {
  const requiredProps = useRequiredInputProps();
  return <input {...requiredProps} className={`rounded-full ${TEXT_FIELD_CLASS} ${className}`} {...props} />;
}
