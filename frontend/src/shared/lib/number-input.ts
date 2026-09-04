// A free-typed numeric field can hold "", "-", "1.2.3", or a pasted
// fragment -- all of which make Number() return NaN, which JSON.stringify
// then silently turns into null on the wire. Parsing here turns that into
// an explicit validation failure the caller rejects the submit on, instead
// of sending a null the backend didn't ask for.

/** Parses a required whole-number field. undefined means invalid input -- reject the submit. */
export function parseRequiredInt(value: string, min: number): number | undefined {
  const parsed = Math.round(Number(value));
  return Number.isFinite(parsed) && parsed >= min ? parsed : undefined;
}

/** Same, but a blank field is valid and means "unset" (null), not invalid. */
export function parseOptionalInt(value: string, min: number): number | null | undefined {
  if (value.trim() === "") return null;
  return parseRequiredInt(value, min);
}
