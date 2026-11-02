import { useRef, type ReactNode } from "react";

import { useNativeFieldError } from "@shared/lib/use-native-field-error";
import { FieldHint } from "@shared/ui/FieldHint";

interface FieldProps {
  label: ReactNode;
  htmlFor?: string;
  /** FieldHint next to the label */
  info?: string;
  /** red asterisk after the label */
  required?: boolean;
  /** full-white label instead of the muted one (settings cards) */
  bright?: boolean;
  /** extra element after the label, e.g. a count Tag */
  aside?: ReactNode;
  /** text under the control */
  hint?: ReactNode;
  /** replaces hint */
  error?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function Field({ label, htmlFor, required = false, bright = false, info, aside, hint, error, className = "", children }: FieldProps) {
  const ref = useRef<HTMLDivElement>(null);
  const nativeError = useNativeFieldError(ref);

  const shownError = error ?? nativeError;
  return (
    <div ref={ref} className={`flex flex-col gap-1 ${className}`}>
      <label htmlFor={htmlFor} className={`flex items-center gap-1.5 text-sm font-medium ${bright ? "text-foreground" : "text-foreground/80"}`}>
        {label}
        {required && <span className="text-error">*</span>}
        {info && <FieldHint text={info} />}
        {aside}
      </label>
      {children}
      {shownError ? (
        <span className="text-[12px] text-error">{shownError}</span>
      ) : (
        hint && <span className="text-[12px] text-muted-foreground">{hint}</span>
      )}
    </div>
  );
}
