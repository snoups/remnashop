import type { TFunction } from "i18next";

// "after" is the form that follows a preposition: «более 41 минуты»
export function formatUptime(t: TFunction, seconds: number, form: "plain" | "after" = "plain"): string {
  const suffix = form === "after" ? "After" : "";
  const unit = (name: "Days" | "Hours" | "Minutes", count: number) =>
    t(`dashboard.runtime.duration${name}${suffix}` as const, { count });
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return hours > 0 ? `${unit("Days", days)} ${unit("Hours", hours)}` : unit("Days", days);
  if (hours > 0) return minutes > 0 ? `${unit("Hours", hours)} ${unit("Minutes", minutes)}` : unit("Hours", hours);
  return unit("Minutes", minutes);
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
