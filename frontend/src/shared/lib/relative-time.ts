import i18n from "@shared/i18n";

/** "5 minutes ago" / "in 3 hours" / "yesterday", in the given UI language. */
export function formatRelative(iso: string, language: string): string {
  const minutes = Math.round((new Date(iso).getTime() - Date.now()) / 60_000);
  // Intl's word for 0 minutes ("в эту минуту") reads oddly in a sentence
  if (minutes === 0) {
    const elapsed = new Date(iso).getTime() <= Date.now();
    return i18n.t(elapsed ? "common.lessThanMinuteAgo" : "common.inLessThanMinute", { lng: language });
  }
  const rtf = new Intl.RelativeTimeFormat(language, { numeric: "auto" });
  if (Math.abs(minutes) < 60) return rtf.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 48) return rtf.format(hours, "hour");
  return rtf.format(Math.round(hours / 24), "day");
}

/** "30.09.2026 23:00" in the given UI language (09/30/2026 11:00 PM in en), for every date with a time. */
export function formatDateTime(iso: string, language: string): string {
  return new Date(iso)
    .toLocaleString(language, { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
    .replace(",", "");
}

/** "23:00" in the given UI language (11:00 PM in en), for a time shown without its date. */
export function formatTime(value: string | Date, language: string): string {
  return new Date(value).toLocaleTimeString(language, { hour: "2-digit", minute: "2-digit" });
}

/** "30.09.2026" in the given UI language, for every date without a time. */
export function formatDate(iso: string, language: string): string {
  return new Date(iso).toLocaleDateString(language, { day: "2-digit", month: "2-digit", year: "numeric" });
}
