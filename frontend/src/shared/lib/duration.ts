import type { TFunction } from "i18next";

// the backend's unlimited expiry: a date the panel needs, read as "never"
const UNLIMITED_EXPIRE_YEAR = 2099;

export function isUnlimitedExpiry(iso: string): boolean {
  return new Date(iso).getUTCFullYear() >= UNLIMITED_EXPIRE_YEAR;
}

/** An expiry to set for "no end date": today's date in that year. */
export function unlimitedExpiry(): string {
  const date = new Date();
  date.setFullYear(UNLIMITED_EXPIRE_YEAR);
  return date.toISOString();
}

/** A plan duration in short form ("30 дн."); 0 days is unlimited. */
export function formatDuration(days: number, t: TFunction): string {
  return days === 0 ? t("plans.forever") : t("plans.daysShort", { count: days });
}

/** A plan duration in words ("30 дней"); 0 days is unlimited. */
export function formatDurationLong(days: number, t: TFunction): string {
  return days === 0 ? t("plans.forever") : t("subscriptions.duration.days", { count: days });
}
