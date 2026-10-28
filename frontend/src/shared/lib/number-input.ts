import type { KeyboardEvent } from "react";

// A free-typed numeric field can hold "", "-" or "1.2.3"; Number() gives NaN,
// which JSON.stringify sends as null. Parsing here makes that a validation
// failure the caller rejects the submit on.

/** Parses a required whole-number field. undefined means invalid input; reject the submit. */
export function parseRequiredInt(value: string, min: number): number | undefined {
  const parsed = Math.round(Number(value));
  return Number.isFinite(parsed) && parsed >= min ? parsed : undefined;
}

/** Same, but a blank field is valid and means "unset" (null), not invalid. */
export function parseOptionalInt(value: string, min: number): number | null | undefined {
  if (value.trim() === "") return null;
  return parseRequiredInt(value, min);
}

/** Display-only: "3.000003" -> "3.00". Callers send the original value back unless the user edited it. */
export function toTwoDecimals(value: string): string {
  return value === "" ? value : Number(value).toFixed(2);
}

// type="number" doesn't filter typed characters everywhere (Firefox and Safari
// take letters too), so only printable keys are checked against a whitelist:
// arrows, Backspace, Tab and Ctrl/Cmd shortcuts pass through, and the
// browser's min/max/step validation stays intact.
const INTEGER_KEY = /^\d$/;
const DECIMAL_KEY = /^[\d.]$/;

function blockKeysOutside(event: KeyboardEvent<HTMLInputElement>, allowed: RegExp): void {
  if (event.key.length !== 1 || event.ctrlKey || event.metaKey) return;
  if (!allowed.test(event.key)) event.preventDefault();
}

export function blockNonIntegerKeys(event: KeyboardEvent<HTMLInputElement>): void {
  blockKeysOutside(event, INTEGER_KEY);
}

export function blockNonDecimalKeys(event: KeyboardEvent<HTMLInputElement>): void {
  blockKeysOutside(event, DECIMAL_KEY);
}
