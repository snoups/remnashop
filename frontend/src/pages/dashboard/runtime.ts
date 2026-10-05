import type { TFunction } from "i18next";

export function formatUptime(t: TFunction, seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) {
    const daysLabel = t("dashboard.runtime.durationDays", { count: days });
    return hours > 0 ? `${daysLabel} ${t("dashboard.runtime.durationHours", { count: hours })}` : daysLabel;
  }
  if (hours > 0) {
    const hoursLabel = t("dashboard.runtime.durationHours", { count: hours });
    return minutes > 0
      ? `${hoursLabel} ${t("dashboard.runtime.durationMinutes", { count: minutes })}`
      : hoursLabel;
  }
  return t("dashboard.runtime.durationMinutes", { count: minutes });
}

// process names are docker-entrypoint.sh's targets, identifiers left untranslated
export const RUNTIME_PROCESS_LABELS: Record<string, string> = {
  api: "API",
  telegram: "Telegram bot",
  worker: "Worker",
  scheduler: "Scheduler",
};

export function usageBarClass(percent: number): string {
  if (percent >= 95) return "bg-error";
  if (percent >= 80) return "bg-warning";
  return "bg-primary";
}
