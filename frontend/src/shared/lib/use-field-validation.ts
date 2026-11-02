import { useCallback, useState } from "react";

/**
 * When a form shows its field errors: not while a field is first typed into, but once it has been
 * left (blur) or a save was tried; from then on on every keystroke, gone as soon as the value is
 * right. The form computes each error itself and asks `visible` whether to show it; a field error
 * the backend returned goes through `setServerError` and clears once that field changes.
 */
export function useFieldValidation<Name extends string>() {
  const [touched, setTouched] = useState<ReadonlySet<Name>>(new Set());
  const [submitted, setSubmitted] = useState(false);
  const [serverErrors, setServerErrors] = useState<Partial<Record<Name, string>>>({});

  /** the error to show under `name`, or undefined */
  const visible = useCallback(
    (name: Name, error: string | null | undefined): string | undefined =>
      serverErrors[name] ?? ((submitted || touched.has(name)) && error ? error : undefined),
    [serverErrors, submitted, touched],
  );

  /** onBlur for the field */
  const touch = useCallback(
    (name: Name) => () => setTouched((prev) => (prev.has(name) ? prev : new Set(prev).add(name))),
    [],
  );

  /** call on every change of the field: drops the backend's error about its old value */
  const changed = useCallback((name: Name) => {
    setServerErrors((prev) => {
      if (!(name in prev)) return prev;
      const { [name]: _dropped, ...rest } = prev;
      return rest as Partial<Record<Name, string>>;
    });
  }, []);

  const setServerError = useCallback((name: Name, message: string) => {
    setServerErrors((prev) => ({ ...prev, [name]: message }));
  }, []);

  /** a save was tried: every error shows */
  const submit = useCallback(() => setSubmitted(true), []);

  /** after a successful save: back to quiet */
  const reset = useCallback(() => {
    setTouched(new Set());
    setSubmitted(false);
    setServerErrors({});
  }, []);

  return { visible, touch, changed, setServerError, submit, reset };
}
