import { useRef, type ReactNode } from "react";

import { useNativeFieldError } from "@shared/lib/use-native-field-error";
import { FieldRequiredContext } from "@shared/ui/field-context";
import { FieldHint } from "@shared/ui/FieldHint";

interface FieldProps {
  label: ReactNode;
  /** the control's id: a click on the label focuses it */
  htmlFor?: string;
  /** red asterisk after the label; the control inside becomes required */
  required?: boolean;
  /** FieldHint next to the label */
  info?: string;
  /** after the label: a count Tag */
  aside?: ReactNode;
  /** under the control */
  hint?: ReactNode;
  /** replaces hint */
  error?: ReactNode;
  children: ReactNode;
}

/** Label over a control (13px medium, on the type scale with the control), hint or error under it. */
export function Field({ label, htmlFor, required = false, info, aside, hint, error, children }: FieldProps) {
  const ref = useRef<HTMLDivElement>(null);
  const nativeError = useNativeFieldError(ref);
  const shownError = error ?? nativeError;
  return (
    <div ref={ref} className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="flex items-center gap-1.5 text-[13px] font-medium text-foreground">
        {label}
        {required && <span className="text-error">*</span>}
        {info && <FieldHint text={info} />}
        {aside}
      </label>
      <FieldRequiredContext.Provider value={required}>{children}</FieldRequiredContext.Provider>
      {shownError ? (
        <span className="text-[12px] text-error">{shownError}</span>
      ) : (
        hint && <span className="text-[12px] text-muted-foreground">{hint}</span>
      )}
    </div>
  );
}
