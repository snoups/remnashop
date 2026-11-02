import { useEffect, useState, type RefObject } from "react";

import { FIELD_INVALID_EVENT, NATIVE_INVALID_ATTR, validationMessage } from "@shared/lib/form-validation";

/** The browser's constraint (required, min, step...) failing on submit inside `ref`, as a message;
 *  re-checked while typing, null once the value passes. See form-validation.ts. */
export function useNativeFieldError(ref: RefObject<HTMLElement | null>): string | null {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const onInvalid = (event: Event) => {
      event.preventDefault();
      setError((event as CustomEvent<string>).detail);
    };
    const onInput = (event: Event) => {
      const el = event.target as HTMLInputElement;
      if (!el.hasAttribute(NATIVE_INVALID_ATTR)) return;
      if (el.validity.valid) {
        el.removeAttribute(NATIVE_INVALID_ATTR);
        setError(null);
      } else {
        setError(validationMessage(el));
      }
    };
    root.addEventListener(FIELD_INVALID_EVENT, onInvalid);
    root.addEventListener("input", onInput);
    return () => {
      root.removeEventListener(FIELD_INVALID_EVENT, onInvalid);
      root.removeEventListener("input", onInput);
    };
  }, [ref]);

  return error;
}
