import type { TFunction } from "i18next";

export interface DayGroup<T> {
  key: string;
  date: Date;
  items: T[];
}

/** Items must arrive newest first: only consecutive ones are grouped. */
export function groupByDay<T>(items: T[], dateOf: (item: T) => string): DayGroup<T>[] {
  const groups: DayGroup<T>[] = [];
  for (const item of items) {
    const date = new Date(dateOf(item));
    const key = date.toDateString();
    const last = groups[groups.length - 1];
    if (last?.key === key) last.items.push(item);
    else groups.push({ key, date, items: [item] });
  }
  return groups;
}

/** "Today", "Yesterday", otherwise "12 March" (with the year when it isn't this one). */
export function formatDayLabel(date: Date, t: TFunction, language: string): string {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return t("common.today");
  if (date.toDateString() === yesterday.toDateString()) return t("common.yesterday");
  return date.toLocaleDateString(language, {
    day: "numeric",
    month: "long",
    year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
  });
}
