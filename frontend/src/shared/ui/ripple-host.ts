/** a press inside one of these is its own, not the host's */
export const INTERACTIVE_SELECTOR = "button, a, input, select, textarea, label, [tabindex]";

/** "relative" unless the caller already positions the element (absolute, fixed, sticky): Ripple's layer needs one */
export function rippleHost(className: string): string {
  return /(^|\s)(absolute|fixed|sticky)(\s|$)/.test(className) ? "" : "relative";
}
