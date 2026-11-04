import type { Plan, PlanAvailability, UpdatePlanAccessRequest } from "@entities/plans/api";

export interface PlanAccessValue {
  availability: PlanAvailability;
  telegramIds: string[];
  emails: string[];
}

export function planAccessValue(plan: Plan | null): PlanAccessValue {
  return {
    availability: plan?.availability ?? "ALL",
    telegramIds: plan?.allowed_telegram_ids.map(String) ?? [],
    emails: plan?.allowed_emails ?? [],
  };
}

export function planAccessPayload({ availability, telegramIds, emails }: PlanAccessValue): UpdatePlanAccessRequest {
  return {
    availability,
    // the lists only mean something for ALLOWED; switching away drops them
    allowed_telegram_ids: availability === "ALLOWED" ? telegramIds.map(Number) : [],
    allowed_emails: availability === "ALLOWED" ? emails : [],
  };
}
