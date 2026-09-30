import i18n from "@shared/i18n";
import { toast } from "@shared/lib/toast";

type Validatable = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

/** Fired on the control; Field listens for it and shows the message under itself. */
export const FIELD_INVALID_EVENT = "field-invalid";
/** Set on a control while its native constraint fails; TextInput draws the error border from it. */
export const NATIVE_INVALID_ATTR = "data-invalid-native";

export function validationMessage(el: Validatable): string {
  const v = el.validity;
  const input = el instanceof HTMLInputElement ? el : null;
  if (v.valueMissing) return i18n.t("errors.validation.required");
  if (v.typeMismatch) return i18n.t(input?.type === "email" ? "errors.validation.email" : "errors.validation.url");
  if (v.rangeUnderflow) return i18n.t("errors.validation.min", { min: input?.min });
  if (v.rangeOverflow) return i18n.t("errors.validation.max", { max: input?.max });
  if (v.stepMismatch) return i18n.t("errors.validation.step", { step: input?.step });
  if (v.patternMismatch) return i18n.t("errors.validation.pattern");
  if (v.tooShort) return i18n.t("errors.validation.tooShort", { count: input?.minLength });
  if (v.badInput) return i18n.t("errors.invalidNumber");
  return i18n.t("errors.validation.generic");
}

let pending = false;

// Browsers draw their own unstyled bubble for required/min/step/pattern/type=url...;
// cancel it: a control inside Field gets the message under itself, anything else a toast.
// Every invalid control of a form fires; only the first one takes the focus.
export function installFormValidationMessages(): void {
  document.addEventListener(
    "invalid",
    (event) => {
      event.preventDefault();
      const el = event.target as Validatable;
      el.setAttribute(NATIVE_INVALID_ATTR, "");
      const message = validationMessage(el);
      const inField = el.dispatchEvent(new CustomEvent(FIELD_INVALID_EVENT, { detail: message, bubbles: true, cancelable: true })) === false;

      if (pending) return;
      pending = true;
      setTimeout(() => (pending = false));
      el.focus();
      if (!inField) toast.error(message);
    },
    true,
  );
}
