import { useEffect, useRef, useState, type ReactNode } from "react";

import { FIELD_INVALID_EVENT, NATIVE_INVALID_ATTR, validationMessage } from "@shared/lib/form-validation";
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
  // the browser's constraint (required, min, step...) failing on submit; see form-validation.ts
  const [nativeError, setNativeError] = useState<string | null>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const onInvalid = (event: Event) => {
      event.preventDefault();
      setNativeError((event as CustomEvent<string>).detail);
    };
    // re-checked while typing, gone once the value passes
    const onInput = (event: Event) => {
      const el = event.target as HTMLInputElement;
      if (!el.hasAttribute(NATIVE_INVALID_ATTR)) return;
      if (el.validity.valid) {
        el.removeAttribute(NATIVE_INVALID_ATTR);
        setNativeError(null);
      } else {
        setNativeError(validationMessage(el));
      }
    };
    root.addEventListener(FIELD_INVALID_EVENT, onInvalid);
    root.addEventListener("input", onInput);
    return () => {
      root.removeEventListener(FIELD_INVALID_EVENT, onInvalid);
      root.removeEventListener("input", onInput);
    };
  }, []);

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
