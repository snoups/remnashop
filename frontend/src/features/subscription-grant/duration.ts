import type { Plan } from "@entities/plans/api";
import { parseRequiredInt } from "@shared/lib/number-input";

export type DurationChoice = { kind: "keep" } | { kind: "plan"; days: number } | { kind: "custom"; days: string };

/** null keeps the current expiry; undefined is invalid input */
export function durationDays(choice: DurationChoice): number | null | undefined {
  if (choice.kind === "keep") return null;
  if (choice.kind === "plan") return choice.days;
  return parseRequiredInt(choice.days, 1);
}

/** the plan's first duration, or a custom field when it has none */
export function defaultDuration(plan: Plan | undefined): DurationChoice {
  const first = plan?.durations[0];
  return first ? { kind: "plan", days: first.days } : { kind: "custom", days: "" };
}
