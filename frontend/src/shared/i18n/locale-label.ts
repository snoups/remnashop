// The bot supports ~40 locales; the browser already knows their names in every
// UI language, so there is no hand-written table to keep in sync.
const formatters = new Map<string, Intl.DisplayNames>();

function formatterFor(uiLanguage: string): Intl.DisplayNames | null {
  const cached = formatters.get(uiLanguage);
  if (cached) return cached;
  try {
    const formatter = new Intl.DisplayNames([uiLanguage], { type: "language" });
    formatters.set(uiLanguage, formatter);
    return formatter;
  } catch {
    return null;
  }
}

/** "ru" -> "Русский" in a Russian UI, "Russian" in an English one. Falls back to
 * the bare code for anything the browser doesn't recognise. */
export function localeLabel(code: string, uiLanguage: string): string {
  let name: string | undefined;
  try {
    name = formatterFor(uiLanguage)?.of(code.toLowerCase());
  } catch {
    name = undefined;
  }
  if (!name || name.toLowerCase() === code.toLowerCase()) return code.toUpperCase();
  return name.charAt(0).toUpperCase() + name.slice(1);
}
